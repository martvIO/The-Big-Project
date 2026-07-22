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

    async def list_tenants(self) -> list[TenantSummary]:
        self.calls.append(("list_tenants", {}))
        return []


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
