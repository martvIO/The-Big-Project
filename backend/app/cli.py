"""Operator CLI for tenant lifecycle (provision / suspend / list / reset-password).

Run over SSH/CI: `python -m app.cli provision --slug bella --name "Bella" \
  --owner-email owner@bella.example`. The password is read from stdin/getpass —
never an argv, which would leak into the process list and shell history.
"""

import argparse
import asyncio
import getpass
import os
import re
import sys
from collections.abc import Callable
from typing import Protocol

from app.platform.service import CommandResult, TenantSummary

PasswordReader = Callable[[], str]

# Strip control chars before printing operator-supplied text — a tab/newline
# corrupts the columnar output and an ANSI sequence could spoof the terminal.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _safe(text: str) -> str:
    return _CONTROL_CHARS.sub(" ", text)


class ProvisioningLike(Protocol):
    async def provision(
        self, *, slug: str, name: str, owner_email: str, owner_password: str, operator: str
    ) -> CommandResult: ...
    async def suspend(self, *, slug: str, operator: str) -> CommandResult: ...
    async def backfill_booking_links(self, *, operator: str) -> CommandResult: ...
    async def run_retention(self, *, operator: str, dry_run: bool) -> CommandResult: ...
    async def reset_owner_password(
        self, *, slug: str, owner_email: str, new_password: str, operator: str
    ) -> CommandResult: ...
    async def list_tenants(self) -> list[TenantSummary]: ...


def build_parser() -> argparse.ArgumentParser:
    default_operator = os.environ.get("USER", "operator")
    parser = argparse.ArgumentParser(prog="app.cli", description="Boutique platform operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    def _with_operator(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--operator", default=default_operator, help="operator identity for the audit trail"
        )

    provision = sub.add_parser("provision", help="create a tenant and its first owner")
    provision.add_argument("--slug", required=True)
    provision.add_argument("--name", required=True)
    provision.add_argument("--owner-email", required=True, dest="owner_email")
    _with_operator(provision)

    suspend = sub.add_parser("suspend", help="suspend a tenant")
    suspend.add_argument("--slug", required=True)
    _with_operator(suspend)

    reset = sub.add_parser("reset-password", help="reset an owner's password")
    reset.add_argument("--slug", required=True)
    reset.add_argument("--owner-email", required=True, dest="owner_email")
    _with_operator(reset)

    listing = sub.add_parser("list", help="list all tenants")
    _with_operator(listing)

    # F16's one-time deploy step: F14 shipped the booking flow before any SMS
    # existed, so confirmed future bookings already exist with no manage link and
    # no reminder. Safe to re-run — the feed is "no token yet".
    backfill = sub.add_parser(
        "backfill-booking-links",
        help="one-time: mint manage links + schedule reminders for existing future bookings",
    )
    _with_operator(backfill)

    # F20's retention run. `--operator` is `required=True` HERE ONLY, deliberately
    # diverging from `_with_operator`'s `$USER` default (D23). The five
    # subcommands above are recoverable or read-only; this one issues an
    # irreversible multi-tenant hard-DELETE, and `$USER` on a shared box is not
    # an audit identity.
    #
    # No `--slug`: the clocks are a duty the platform enforces on every
    # controller's behalf, and a per-tenant flag would make a legal obligation a
    # checklist.
    retention = sub.add_parser(
        "retention", help="run the per-data-class retention job across every tenant"
    )
    retention.add_argument(
        "--operator", required=True, help="operator identity for the audit trail"
    )
    # ⚠ THE REHEARSAL IS THE DEFAULT AND ARMING IS THE DELIBERATE ACT.
    #
    # `run_retention` is deliberately NOT gated on `retention_enabled`, so this
    # subcommand is the one place where Gate 1 Q2's disarm — the whole reason the
    # scheduled job ships off, pending F21's tested restore — can be defeated by
    # one command. With `--dry-run` opt-in, the command an operator types from
    # memory was the irreversible multi-tenant hard DELETE and the safe one was
    # the one they had to remember. Inverted: `--armed` is a sentence you cannot
    # type by accident, and a mistyped rehearsal now counts rows instead of
    # destroying them.
    retention.add_argument(
        "--armed",
        action="store_true",
        help="actually delete. Without it the run only counts what each policy would touch",
    )

    return parser


def _report(result: CommandResult) -> int:
    if result.ok:
        suffix = f" ({result.tenant_id})" if result.tenant_id else ""
        print(f"OK: {result.message}{suffix}")
        return 0
    print(f"FAILED: {result.message}", file=sys.stderr)
    return 1


def _print_tenants(rows: list[TenantSummary]) -> None:
    if not rows:
        print("(no tenants)")
        return
    for r in rows:
        print(f"{r.slug}\t{r.status}\t{_safe(r.name)}\t{r.created_at.isoformat()}")


async def _dispatch(
    args: argparse.Namespace, service: ProvisioningLike, read_password: PasswordReader
) -> int:
    if args.command == "provision":
        return _report(
            await service.provision(
                slug=args.slug,
                name=args.name,
                owner_email=args.owner_email,
                owner_password=read_password(),
                operator=args.operator,
            )
        )
    if args.command == "suspend":
        return _report(await service.suspend(slug=args.slug, operator=args.operator))
    if args.command == "reset-password":
        return _report(
            await service.reset_owner_password(
                slug=args.slug,
                owner_email=args.owner_email,
                new_password=read_password(),
                operator=args.operator,
            )
        )
    if args.command == "backfill-booking-links":
        return _report(await service.backfill_booking_links(operator=args.operator))
    if args.command == "retention":
        return _report(await service.run_retention(operator=args.operator, dry_run=not args.armed))
    if args.command == "list":
        _print_tenants(await service.list_tenants())
        return 0
    return 2


def run(args: argparse.Namespace, service: ProvisioningLike, read_password: PasswordReader) -> int:
    return asyncio.run(_dispatch(args, service, read_password))


def _read_password() -> str:
    if sys.stdin.isatty():
        return getpass.getpass("Password: ")
    return sys.stdin.readline().rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    from app.db.session import ensure_safe_database_role, get_session_factory
    from app.platform.service import ProvisioningService

    args = build_parser().parse_args(argv)

    async def _bootstrap() -> int:
        # Same fail-fast as the web app: an operator using personal elevated creds
        # can't silently void the WITH CHECK isolation net.
        await ensure_safe_database_role()
        service = ProvisioningService(get_session_factory())
        return await _dispatch(args, service, _read_password)

    return asyncio.run(_bootstrap())


if __name__ == "__main__":
    sys.exit(main())
