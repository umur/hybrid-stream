import msgpack
from aiokafka import AIOKafkaProducer


class BridgeProducer:
    def __init__(self, bootstrap_servers: str):
        self._bootstrap = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            compression_type="lz4",
            acks="all",
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def send(self, topic: str, record: dict) -> None:
        if not self._producer:
            raise RuntimeError("BridgeProducer not started")
        payload = msgpack.packb(record, use_bin_type=True)
        await self._producer.send_and_wait(topic, payload)

    async def send_raw(self, topic: str, payload: bytes) -> None:
        if not self._producer:
            raise RuntimeError("BridgeProducer not started")
        await self._producer.send_and_wait(topic, payload)
