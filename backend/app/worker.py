"""Worker entrypoint. Pollers (scheduled messages, hold sweeper, offer cascade)
register here in later features — for now it only proves the process model."""

import asyncio
import logging

logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 60


async def main() -> None:
    logger.info("worker started — no jobs registered yet")
    while True:  # noqa: ASYNC110 — placeholder loop until first poller lands
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
