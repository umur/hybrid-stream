import asyncio
import logging
import signal
import sys

from .config import AODEConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


class AODEService:
    def __init__(self) -> None:
        self.config = AODEConfig()

    async def run(self) -> None:
        log.info("AODE service starting with instance_id=%s", self.config.instance_id)
        # Components will be initialized here when integrated
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            log.info("AODE service shutting down")


def main() -> None:
    service = AODEService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        log.info("Interrupted")


if __name__ == "__main__":
    main()
