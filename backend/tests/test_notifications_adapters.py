import pytest

from app.notifications.base import SendResult, SmsNotConfiguredError, SmsSender
from app.notifications.fake import FakeSmsSender
from app.notifications.unconfigured import UnconfiguredSmsSender


async def test_fake_captures_sends_in_order() -> None:
    sender = FakeSmsSender()
    result_one = await sender.send(phone="+972501234567", body="ראשון")
    result_two = await sender.send(phone="+972521234567", body="שני")
    assert [(item.phone, item.body) for item in sender.outbox] == [
        ("+972501234567", "ראשון"),
        ("+972521234567", "שני"),
    ]
    assert isinstance(result_one, SendResult)
    assert result_one.provider_message_id is not None
    assert result_one.provider_message_id != result_two.provider_message_id


async def test_fake_is_configured() -> None:
    assert FakeSmsSender().is_configured is True


async def test_unconfigured_raises_and_reports() -> None:
    sender = UnconfiguredSmsSender()
    assert sender.is_configured is False
    with pytest.raises(SmsNotConfiguredError):
        await sender.send(phone="+972501234567", body="x")


def test_adapters_satisfy_the_protocol() -> None:
    # Protocol conformance is structural; assigning to the annotation is the check.
    fake: SmsSender = FakeSmsSender()
    unconfigured: SmsSender = UnconfiguredSmsSender()
    assert fake is not unconfigured
