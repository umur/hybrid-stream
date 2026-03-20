import asyncio
import logging
import time
from typing import Dict, List, Optional

try:
    import etcd3
except ImportError:
    etcd3 = None  # Will be mocked in tests

log = logging.getLogger(__name__)


class EtcdClient:
    def __init__(self, endpoints: List[str], key_prefix: str) -> None:
        self._endpoints = endpoints
        self._prefix = key_prefix
        self._client = None
        self._lease = None

    async def connect(self) -> None:
        host, port = self._endpoints[0].split(":")
        self._client = etcd3.client(host=host, port=int(port))

    async def close(self) -> None:
        if self._lease:
            self._lease.revoke()
        if self._client:
            self._client.close()

    def put(self, key: str, value: str) -> None:
        full_key = f"{self._prefix}{key}"
        self._client.put(full_key, value)

    def get(self, key: str) -> Optional[str]:
        full_key = f"{self._prefix}{key}"
        result, _ = self._client.get(full_key)
        return result.decode() if result else None

    def delete(self, key: str) -> None:
        full_key = f"{self._prefix}{key}"
        self._client.delete(full_key)

    def get_dict(self, key_prefix: str) -> Dict[str, str]:
        full_prefix = f"{self._prefix}{key_prefix}"
        results = self._client.get_prefix(full_prefix)
        kv_dict = {}
        for value, metadata in results:
            full_key = metadata.key.decode()
            suffix = full_key[len(full_prefix):].lstrip("/")
            if suffix:
                kv_dict[suffix] = value.decode()
        return kv_dict

    async def acquire_leader_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        lock_key = f"{self._prefix}leaders/{lock_name}"
        lease = self._client.lease(ttl_seconds)
        self._lease = lease
        try:
            success = self._client.transaction(
                compare=[self._client.transactions.create(lock_key) == 0],
                success=[self._client.transactions.put(lock_key, f"leader-{int(time.time())}", lease=lease)],
                failure=[],
            )
            if success:
                return True
            return False
        except Exception as e:
            log.error("Leader election error: %s", e)
            return False

    async def release_leader_lock(self) -> None:
        if self._lease:
            self._lease.revoke()
            self._lease = None

    async def maintain_leadership(self, lock_name: str, ttl_seconds: int = 30) -> None:
        if not self._lease:
            raise ValueError("No active lease to maintain")
        while True:
            await asyncio.sleep(ttl_seconds // 3)
            self._lease.refresh()


class LeaderElection:
    def __init__(self, etcd_client, instance_id: str) -> None:
        self._etcd = etcd_client
        self._instance_id = instance_id
        self._is_leader: bool = False
        self._leadership_task: Optional[asyncio.Task] = None

    async def start_election(self) -> bool:
        is_leader = await self._etcd.acquire_leader_lock("aode", ttl_seconds=30)
        if is_leader:
            self._is_leader = True
            self._leadership_task = asyncio.create_task(
                self._etcd.maintain_leadership("aode", ttl_seconds=30)
            )
        return is_leader

    async def stop_election(self) -> None:
        if self._leadership_task:
            self._leadership_task.cancel()
            try:
                await self._leadership_task
            except asyncio.CancelledError:
                pass
        if self._is_leader:
            await self._etcd.release_leader_lock()
            self._is_leader = False

    def is_leader(self) -> bool:
        return self._is_leader
