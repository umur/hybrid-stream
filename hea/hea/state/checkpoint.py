import asyncio
import logging
import os
from .store import OperatorStateStore

log = logging.getLogger(__name__)


class PeriodicCheckpointer:
    def __init__(self, interval_s: int, checkpoint_base_dir: str):
        self._interval = interval_s
        self._base_dir = checkpoint_base_dir
        self._stores: dict[str, OperatorStateStore] = {}
        self._task: asyncio.Task | None = None

    def register(self, operator_id: str, store: OperatorStateStore) -> None:
        self._stores[operator_id] = store

    def deregister(self, operator_id: str) -> None:
        self._stores.pop(operator_id, None)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            for oid, store in list(self._stores.items()):
                try:
                    path = store.checkpoint(os.path.join(self._base_dir, "checkpoints"))
                    log.debug("Checkpoint created for %s at %s", oid, path)
                except Exception as e:
                    log.error("Checkpoint failed for %s: %s", oid, e)
