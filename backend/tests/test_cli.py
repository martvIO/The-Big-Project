import uuid

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
    # The parser must have no --password/--owner-password option (leak via argv).
    actions = {a.dest for a in build_parser()._subparsers._group_actions}  # type: ignore[union-attr]
    help_text = build_parser().format_help()
    assert "--password" not in help_text
    assert "--owner-password" not in help_text
    _ = actions


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
