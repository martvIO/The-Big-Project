import contextlib
import io
from collections.abc import Iterator

import pytest

from app.cli import build_parser, run
from app.platform.service import CommandResult


class FakeService:
    def __init__(self, result: CommandResult | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._result = result or CommandResult(ok=True, message="done")

    async def backfill_booking_links(self, **kwargs: object) -> CommandResult:
        self.calls.append(("backfill_booking_links", kwargs))
        return self._result

    async def run_retention(self, **kwargs: object) -> CommandResult:
        self.calls.append(("run_retention", kwargs))
        return self._result

    async def create_operator(self, **kwargs: object) -> CommandResult:
        self.calls.append(("create_operator", kwargs))
        return self._result

    async def deactivate_operator(self, **kwargs: object) -> CommandResult:
        self.calls.append(("deactivate_operator", kwargs))
        return self._result


def _dispatch(argv: list[str], service: FakeService, password: str = "pw") -> int:
    args = build_parser().parse_args(argv)
    return run(args, service, lambda: password)


def test_backfill_booking_links_maps_through_and_reads_no_password() -> None:
    """F16's one-time deploy step (Interview pre-decided #9). It touches every
    tenant's bookings, so it takes an operator for the audit row — and, like
    `list`, it must never prompt for a password: a command run from a deploy hook
    that blocks on getpass hangs the deploy."""
    service = FakeService(CommandResult(ok=True, message="backfilled 3 manage link(s)"))

    def _no_password() -> str:
        raise AssertionError("backfill-booking-links must not read a password")

    args = build_parser().parse_args(["backfill-booking-links", "--operator", "ops"])
    assert run(args, service, _no_password) == 0
    assert service.calls == [("backfill_booking_links", {"operator": "ops"})]


def test_backfill_failure_is_a_nonzero_exit() -> None:
    """A deploy hook has to be able to see it failed."""
    service = FakeService(CommandResult(ok=False, message="boom"))
    assert _dispatch(["backfill-booking-links"], service) == 1


def test_backfill_takes_no_slug() -> None:
    """It is platform-wide by design: every active tenant has pre-F16 bookings,
    and a per-tenant flag would make the one-time run a checklist."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["backfill-booking-links", "--slug", "bella"])


# --- F20's retention run -----------------------------------------------------


def test_retention_reads_no_password() -> None:
    """Like `list` and the backfill it must never prompt: a command run from a
    deploy hook that blocks on getpass hangs the deploy."""
    service = FakeService(CommandResult(ok=True, message="would touch 12 row(s)"))

    def _no_password() -> str:
        raise AssertionError("retention must not read a password")

    args = build_parser().parse_args(["retention", "--operator", "ops", "--armed"])
    assert run(args, service, _no_password) == 0
    assert service.calls == [("run_retention", {"operator": "ops", "dry_run": False})]


def test_retention_defaults_to_a_rehearsal_and_arming_is_explicit() -> None:
    """⚠ INVERTED, deliberately. `run_retention` is not gated on
    `retention_enabled`, so this subcommand is the one place Gate 1 Q2's disarm
    can be defeated — and with `--dry-run` opt-in, the command typed from memory
    was the irreversible multi-tenant hard DELETE while the safe one was the one
    you had to remember. A mistyped rehearsal now counts rows."""
    service = FakeService()
    assert _dispatch(["retention", "--operator", "ops"], service) == 0
    assert service.calls[-1][1]["dry_run"] is True

    assert _dispatch(["retention", "--operator", "ops", "--armed"], service) == 0
    assert service.calls[-1][1]["dry_run"] is False


def test_retention_requires_an_explicit_operator() -> None:
    """D23's deliberate divergence from `_with_operator`, which defaults to
    `$USER`. `$USER` on a shared box is not an audit identity, and this is the one
    subcommand that issues an irreversible multi-tenant hard-DELETE."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["retention"])


def test_retention_takes_no_slug() -> None:
    """Platform-wide by design: the clocks are a duty the platform enforces on
    every controller's behalf, and a per-tenant flag would make a legal obligation
    a checklist."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["retention", "--operator", "ops", "--slug", "bella"])


def test_retention_failure_is_a_nonzero_exit() -> None:
    """The CLI half only. That `run_retention` can actually PRODUCE `ok=False` —
    it could not, before: `ok=True` was unconditional and `failed_tenants`
    reached the message and nothing else — is
    `test_retention_db.test_a_run_with_a_failing_tenant_is_not_ok`."""
    service = FakeService(CommandResult(ok=False, message="boom"))
    assert _dispatch(["retention", "--operator", "ops"], service) == 1


# --- F25's operator bootstrap ------------------------------------------------
#
# ⚠ THE ONLY WAY AN OPERATOR IS EVER CREATED. Spec D2: no HTTP route mints or
# edits one, so the console's own compromise cannot make a second operator. That
# makes this pair the highest-privilege surface in the CLI, and the tests below
# are shaped by that rather than by symmetry with the tenant commands.


def test_create_operator_maps_args_and_reads_the_password_from_stdin() -> None:
    """F6's rule, inherited whole: the password never touches argv, where it
    would land in the process list and the shell history of a shared box."""
    service = FakeService()
    args = build_parser().parse_args(
        [
            "create-operator",
            "--email",
            "dana@modryn.example",
            "--display-name",
            "Dana",
            "--operator",
            "ops",
        ]
    )
    assert run(args, service, lambda: "op-console-pw") == 0
    assert service.calls == [
        (
            "create_operator",
            {
                "email": "dana@modryn.example",
                "display_name": "Dana",
                "password": "op-console-pw",
                "operator": "ops",
            },
        )
    ]


def test_neither_operator_command_accepts_a_password_flag() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["create-operator", "--email", "d@x.co", "--display-name", "D", "--password", "x"]
        )


def test_both_operator_commands_require_an_explicit_operator() -> None:
    """The `retention` precedent (D23), and it binds harder here. `_with_operator`
    defaults to `$USER`, which is not an audit identity on a shared box — and the
    act being recorded is the creation or destruction of the credential that
    controls every boutique on the platform."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["create-operator", "--email", "d@x.co", "--display-name", "D"])
    with pytest.raises(SystemExit):
        parser.parse_args(["deactivate-operator", "--email", "d@x.co"])


def test_deactivate_operator_maps_through_and_reads_no_password() -> None:
    """No password to read — deactivation proves nothing about the operator being
    removed, and prompting for one would hang a scripted revocation."""
    service = FakeService()

    def _no_password() -> str:
        raise AssertionError("deactivate-operator must not read a password")

    args = build_parser().parse_args(
        ["deactivate-operator", "--email", "dana@modryn.example", "--operator", "ops"]
    )
    assert run(args, service, _no_password) == 0
    assert service.calls == [
        ("deactivate_operator", {"email": "dana@modryn.example", "operator": "ops"})
    ]


def test_a_refused_operator_command_is_a_nonzero_exit() -> None:
    """A duplicate active email and the last-operator refusal both arrive as
    `CommandResult(ok=False)`. A shell that cannot see the refusal is how a
    bootstrap script "succeeds" without creating anybody."""
    service = FakeService(CommandResult(ok=False, message="operator_email_taken"))
    assert (
        _dispatch(
            ["create-operator", "--email", "d@x.co", "--display-name", "D", "--operator", "ops"],
            service,
        )
        == 1
    )
    service = FakeService(CommandResult(ok=False, message="last_operator"))
    assert (
        _dispatch(["deactivate-operator", "--email", "d@x.co", "--operator", "ops"], service) == 1
    )


# --- F25's parity deletion ---------------------------------------------------


@contextlib.contextmanager
def _stderr() -> Iterator[io.StringIO]:
    """argparse writes its refusal to stderr and then exits; capsys cannot be
    read inside a `pytest.raises` block, so the stream is swapped instead."""
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        yield buffer


def test_the_four_lifecycle_subcommands_are_gone() -> None:
    """⚠ THIS IS THE POINT OF PRE-DECIDED #20, and the deletion is deliberate
    rather than incidental: two doors to the same audited operation is how they
    drift, and the CLI's door needs a shell on the host.

    Parity was proved BEFORE the door was closed —
    `test_platform_console_db.py::test_the_whole_console_lifecycle_writes_the_same
    _book_the_cli_wrote` drives all four over HTTP as `boutique_app` and asserts
    the same `platform_audit_log` rows, with the operator column now carrying an
    authenticated identity instead of `$USER`.

    ⚠ THE ASSERTION IS ON THE MESSAGE, not merely on SystemExit. `provision`,
    `suspend` and `reset-password` all had REQUIRED flags, so
    `parse_args(["provision"])` exited 2 before this feature as well — a bare
    `pytest.raises(SystemExit)` would have been green against the old parser for
    three of the four and would have proved nothing. "invalid choice" is the
    string argparse produces only when the subcommand itself is gone.

    That is also what a stale runbook or a deploy hook still calling one now
    gets — loudly, rather than a shell that quietly does nothing."""
    parser = build_parser()
    for gone in ("provision", "suspend", "reset-password", "list"):
        with pytest.raises(SystemExit), _stderr() as captured:
            parser.parse_args([gone])
        assert "invalid choice" in captured.getvalue(), gone


def test_the_surviving_commands_still_parse() -> None:
    """The CLI FILE survives (spec conflict 1). #20's parity set is the four
    lifecycle operations, and the commands below are not in it: the backfill is
    F16's one-time deploy step, retention is F20's `--armed` rehearsal whose R12
    posture is deliberately shell-only, and the operator pair is F25's own
    bootstrap — the console must not be able to mint its own operators."""
    parser = build_parser()
    assert parser.parse_args(["backfill-booking-links"]).operator
    assert parser.parse_args(["retention", "--operator", "ops"]).operator == "ops"
    assert (
        parser.parse_args(
            ["create-operator", "--email", "d@x.co", "--display-name", "D", "--operator", "ops"]
        ).email
        == "d@x.co"
    )
    assert (
        parser.parse_args(["deactivate-operator", "--email", "d@x.co", "--operator", "ops"]).email
        == "d@x.co"
    )
