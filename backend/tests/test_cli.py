import uuid

import pytest

from app.cli import build_parser, run
from app.platform.service import CommandResult, TenantSummary


class FakeService:
    def __init__(self, result: CommandResult | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._result = result or CommandResult(ok=True, message="done")

    async def provision(self, **kwargs: object) -> CommandResult:
        self.calls.append(("provision", kwargs))
        return self._result

    async def suspend(self, **kwargs: object) -> CommandResult:
        self.calls.append(("suspend", kwargs))
        return self._result

    async def reset_owner_password(self, **kwargs: object) -> CommandResult:
        self.calls.append(("reset_owner_password", kwargs))
        return self._result

    async def list_tenants(self, **kwargs: object) -> list[TenantSummary]:
        self.calls.append(("list_tenants", kwargs))
        return []

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


def test_provision_maps_args_and_reads_password_from_stdin() -> None:
    service = FakeService(CommandResult(ok=True, message="ok", tenant_id=uuid.uuid4()))
    code = _dispatch(
        ["provision", "--slug", "bella", "--name", "Bella", "--owner-email", "o@b.example"],
        service,
        password="s3cret",
    )
    assert code == 0
    name, kwargs = service.calls[0]
    assert name == "provision"
    assert kwargs["slug"] == "bella"
    assert kwargs["owner_email"] == "o@b.example"
    assert kwargs["owner_password"] == "s3cret"  # from the reader, never argv


def test_password_is_not_a_cli_argument() -> None:
    # No subcommand accepts a password flag — it must come from stdin only, never
    # argv (argv leaks into the process list and shell history). argparse exits
    # non-zero on an unrecognized argument, which proves the flag doesn't exist.
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "provision",
                "--slug",
                "b",
                "--name",
                "n",
                "--owner-email",
                "o@e.co",
                "--password",
                "x",
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["reset-password", "--slug", "b", "--owner-email", "o@e.co", "--owner-password", "x"]
        )


def test_failure_result_is_nonzero_exit() -> None:
    service = FakeService(CommandResult(ok=False, message="slug_taken"))
    code = _dispatch(
        ["provision", "--slug", "admin", "--name", "X", "--owner-email", "o@b.example"], service
    )
    assert code == 1


def test_suspend_and_reset_map_through() -> None:
    service = FakeService()
    assert _dispatch(["suspend", "--slug", "bella"], service) == 0
    assert service.calls[-1][0] == "suspend"
    assert (
        _dispatch(
            ["reset-password", "--slug", "bella", "--owner-email", "o@b.example"],
            service,
            password="new-pw",
        )
        == 0
    )
    name, kwargs = service.calls[-1]
    assert name == "reset_owner_password"
    assert kwargs["new_password"] == "new-pw"


def test_list_does_not_read_password() -> None:
    service = FakeService()
    called = {"read": False}

    def reader() -> str:
        called["read"] = True
        return "x"

    args = build_parser().parse_args(["list"])
    assert run(args, service, reader) == 0
    assert service.calls[-1][0] == "list_tenants"
    # F21 D6: `list` is a full cross-tenant read and now carries the operator
    # through to a platform_audit_log row. `--operator` was parsed and discarded
    # before F21, which is the whole finding.
    assert service.calls[-1][1] == {"operator": args.operator}
    assert called["read"] is False


def test_operator_defaults_but_is_overridable() -> None:
    service = FakeService()
    _dispatch(["suspend", "--slug", "bella", "--operator", "ci-bot"], service)
    assert service.calls[-1][1]["operator"] == "ci-bot"


def test_list_output_strips_control_chars(capsys: object) -> None:
    import datetime

    from app.cli import _print_tenants

    _print_tenants(
        [
            TenantSummary(
                slug="bella",
                name="Bella\t\x1b[31mEVIL\nName",
                status="active",
                created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            )
        ]
    )
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    line = out.splitlines()[0]
    # Exactly the 3 intended column tabs; no stray tab/newline/ESC from the name.
    assert line.count("\t") == 3
    assert "\x1b" not in line
    assert "EVIL" in line


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


def test_the_five_older_subcommands_still_default_their_operator() -> None:
    """Asserted BESIDE the requirement above so the divergence reads as intent
    rather than as an inconsistency someone will "fix". `provision`, `suspend`,
    `reset-password`, `list` and `backfill-booking-links` are recoverable or
    read-only; this one is not."""
    parser = build_parser()
    for argv in (
        ["provision", "--slug", "b", "--name", "n", "--owner-email", "o@e.co"],
        ["suspend", "--slug", "b"],
        ["reset-password", "--slug", "b", "--owner-email", "o@e.co"],
        ["list"],
        ["backfill-booking-links"],
    ):
        assert parser.parse_args(argv).operator


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
