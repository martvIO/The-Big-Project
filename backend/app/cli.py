"""Operator CLI — the MAINTENANCE surface, run over SSH/CI.

⚠ THE FOUR TENANT-LIFECYCLE SUBCOMMANDS ARE GONE (F25, pre-decided #20).
`provision`, `suspend`, `list` and `reset-password` moved to the web console at
`admin.{base_domain}/platform`, and they were DELETED here rather than left as a
second door: two doors to the same audited operation is how the two drift, and
this one needs a shell on the host. Parity was proved before the door closed —
`tests/test_platform_console_db.py` drives all four over HTTP as `boutique_app`
and asserts the same `platform_audit_log` rows, with `operator` now carrying an
authenticated identity instead of `$USER`.

What survives, and why each one is NOT in #20's parity set:

* `backfill-booking-links` — F16's one-time deploy step, run once from a hook.
* `retention` — F20's `--armed` rehearsal. R12's closed reading of
  "access-restricted" MEANS a shell on the host, and the ergonomics are the
  control.
* `create-operator` / `deactivate-operator` — F25's own bootstrap. No HTTP route
  mints an operator, so the console's compromise cannot make a second one.

The password is read from stdin/getpass — never an argv, which would leak into
the process list and shell history.
"""

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Callable
from typing import Protocol

from app.platform.service import CommandResult

PasswordReader = Callable[[], str]


class ProvisioningLike(Protocol):
    async def backfill_booking_links(self, *, operator: str) -> CommandResult: ...
    async def run_retention(self, *, operator: str, dry_run: bool) -> CommandResult: ...
    async def create_operator(
        self, *, email: str, display_name: str, password: str, operator: str
    ) -> CommandResult: ...
    async def deactivate_operator(self, *, email: str, operator: str) -> CommandResult: ...


def build_parser() -> argparse.ArgumentParser:
    default_operator = os.environ.get("USER", "operator")
    parser = argparse.ArgumentParser(prog="app.cli", description="Boutique platform operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    def _with_operator(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--operator", default=default_operator, help="operator identity for the audit trail"
        )

    # F16's one-time deploy step: F14 shipped the booking flow before any SMS
    # existed, so confirmed future bookings already exist with no manage link and
    # no reminder. Safe to re-run — the feed is "no token yet".
    backfill = sub.add_parser(
        "backfill-booking-links",
        help="one-time: mint manage links + schedule reminders for existing future bookings",
    )
    _with_operator(backfill)

    # F20's retention run. `--operator` is `required=True`, deliberately diverging
    # from `_with_operator`'s `$USER` default (D23): the backfill above is
    # re-runnable, this one issues an irreversible multi-tenant hard-DELETE, and
    # `$USER` on a shared box is not an audit identity. (It said "the five
    # subcommands above" until F25 deleted four of them; the argument is unchanged
    # and the count was the only thing that rotted.)
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

    # F25's bootstrap pair, and THE CLI IS THE ONLY DOOR (spec D2). No HTTP route
    # creates, edits or deactivates an operator — so a compromised console cannot
    # mint a second operator, and the account list is not reachable over HTTP at
    # all. That is also most of D6's argument for shipping without TOTP.
    #
    # `--operator required=True` on BOTH, the `retention` divergence rather than
    # `_with_operator`'s `$USER` default, and for a sharper reason than
    # retention's: the act being recorded is the creation or destruction of the
    # credential that controls every boutique on the platform. `$USER` on a
    # shared box is not an audit identity for that.
    create_operator = sub.add_parser(
        "create-operator", help="create a platform console operator (password via stdin)"
    )
    create_operator.add_argument("--email", required=True)
    create_operator.add_argument("--display-name", required=True, dest="display_name")
    create_operator.add_argument(
        "--operator", required=True, help="operator identity for the audit trail"
    )

    deactivate_operator = sub.add_parser(
        "deactivate-operator", help="deactivate an operator and revoke every live session"
    )
    deactivate_operator.add_argument("--email", required=True)
    deactivate_operator.add_argument(
        "--operator", required=True, help="operator identity for the audit trail"
    )

    return parser


def _report(result: CommandResult) -> int:
    if result.ok:
        suffix = f" ({result.tenant_id})" if result.tenant_id else ""
        print(f"OK: {result.message}{suffix}")
        return 0
    print(f"FAILED: {result.message}", file=sys.stderr)
    return 1


async def _dispatch(
    args: argparse.Namespace, service: ProvisioningLike, read_password: PasswordReader
) -> int:
    if args.command == "backfill-booking-links":
        return _report(await service.backfill_booking_links(operator=args.operator))
    if args.command == "retention":
        return _report(await service.run_retention(operator=args.operator, dry_run=not args.armed))
    if args.command == "create-operator":
        # stdin/getpass, never argv — F6's rule, now carried by the one password
        # left in this file, which is also the one that opens every boutique.
        return _report(
            await service.create_operator(
                email=args.email,
                display_name=args.display_name,
                password=read_password(),
                operator=args.operator,
            )
        )
    if args.command == "deactivate-operator":
        # Reads no password — deactivation proves nothing about the operator
        # being removed, and a prompt would hang a scripted revocation at the
        # moment somebody most needs it to finish.
        return _report(await service.deactivate_operator(email=args.email, operator=args.operator))
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
