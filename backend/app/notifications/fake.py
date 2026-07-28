"""In-memory sender for dev, tests, and staging until the real adapter lands.
The outbox is what the db suite asserts against, and on staging the INFO line
is the only place the (masked-elsewhere) body is observable."""

import dataclasses
import itertools
import logging

from app.notifications.base import SendResult

logger = logging.getLogger("app")


@dataclasses.dataclass(frozen=True)
class SentSms:
    phone: str
    body: str


class FakeSmsSender:
    def __init__(self) -> None:
        self.outbox: list[SentSms] = []
        self._counter = itertools.count(1)

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, *, phone: str, body: str) -> SendResult:
        self.outbox.append(SentSms(phone=phone, body=body))
        message_id = f"fake-{next(self._counter)}"
        # The body is NOT logged. Staging runs this adapter on a publicly
        # reachable host, and its log stream is widely readable — an INFO line
        # carrying the live code (and the customer's number) would hand
        # verification to anyone with log access, defeating the masking that
        # message_log does two layers up. The outbox is how tests read bodies.
        logger.info("fake SMS %s queued (%d chars)", message_id, len(body))
        return SendResult(provider_message_id=message_id)
