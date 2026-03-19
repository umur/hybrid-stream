from __future__ import annotations
import asyncio
import time
import os
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from aiokafka import AIOKafkaConsumer
from .base_operator import BaseOperator
from .decorators import is_cpu_bound
from ..kafka.producer import BridgeProducer
from ..metrics import HEAMetrics
from ..config import HEAConfig

log = logging.getLogger(__name__)


class OperatorEngine:
    def __init__(self, config: HEAConfig, metrics: HEAMetrics, bridge_producer: BridgeProducer):
        self._config = config
        self._metrics = metrics
        self._bridge = bridge_producer
        self._pool: ProcessPoolExecutor | None = None
        self._operators:      dict[str, BaseOperator] = {}
        self._topic_bindings: dict[str, list[str]]    = {}
        self._output_routes:  dict[str, list[str]]    = {}
        self._consumers:      dict[str, AIOKafkaConsumer] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._worker_queues:  dict[str, asyncio.Queue] = {}
        self._paused_topics:  set[str] = set()
        self._running = False

    async def start(self) -> None:
        self._pool = ProcessPoolExecutor(
            max_workers=max(1, (os.cpu_count() or 2) - 1)
        )
        self._running = True
        log.info("OperatorEngine started. Pool size: %d", self._pool._max_workers)

    async def stop(self) -> None:
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
        if self._pool:
            self._pool.shutdown(wait=False)
        for consumer in self._consumers.values():
            await consumer.stop()
        log.info("OperatorEngine stopped.")

    async def register_operator(
        self,
        operator: BaseOperator,
        input_topics: list[str],
        output_topics: list[str],
    ) -> None:
        oid = operator.operator_id
        self._operators[oid] = operator
        self._output_routes[oid] = output_topics

        for topic in input_topics:
            self._topic_bindings.setdefault(topic, []).append(oid)
            if topic not in self._consumers:
                await self._start_consumer(topic)

        if is_cpu_bound(type(operator)):
            self._worker_queues[oid] = asyncio.Queue()
            asyncio.create_task(self._cpu_worker_loop(oid))

        operator.on_start()
        log.info("Registered operator %s on topics %s", oid, input_topics)

    async def deregister_operator(self, operator_id: str, flush_state: bool = True) -> None:
        if operator_id not in self._operators:
            return
        op = self._operators.pop(operator_id)
        op.on_stop()
        if operator_id in self._worker_queues:
            q = self._worker_queues.pop(operator_id)
            await q.join()
        self._output_routes.pop(operator_id, None)
        log.info("Deregistered operator %s", operator_id)

    async def _start_consumer(self, topic: str) -> None:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._config.kafka_bootstrap,
            group_id=f"{self._config.kafka_group_prefix}-{self._config.node_id}",
            enable_auto_commit=False,
            max_poll_records=self._config.kafka_batch_size,
        )
        await consumer.start()
        self._consumers[topic] = consumer
        task = asyncio.create_task(self._consume_loop(topic))
        self._consumer_tasks[topic] = task
        log.debug("Started consumer for topic: %s", topic)

    async def _consume_loop(self, topic: str) -> None:
        consumer = self._consumers[topic]
        while self._running:
            try:
                records = await consumer.getmany(timeout_ms=100, max_records=self._config.kafka_batch_size)
                for tp, messages in records.items():
                    for msg in messages:
                        record = self._deserialize_record(msg.value)
                        for oid in self._topic_bindings.get(topic, []):
                            await self._dispatch(oid, record, msg.offset)
                await self._check_backpressure(topic)
                await consumer.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Consumer error on topic %s: %s", topic, e)

    async def _dispatch(self, operator_id: str, record: dict, offset: int) -> None:
        op = self._operators.get(operator_id)
        if not op:
            return
        start_ns = time.monotonic_ns()
        if is_cpu_bound(type(op)):
            q = self._worker_queues.get(operator_id)
            if q:
                await q.put((op, record, offset, start_ns))
        else:
            try:
                output_records = await op.process(record)
                await self._emit(operator_id, output_records)
                latency_ms = (time.monotonic_ns() - start_ns) / 1e6
                self._metrics.record_latency(operator_id, latency_ms)
            except Exception as e:
                log.error("Operator %s error: %s", operator_id, e)

    async def _cpu_worker_loop(self, operator_id: str) -> None:
        q = self._worker_queues[operator_id]
        loop = asyncio.get_event_loop()
        while self._running or not q.empty():
            try:
                op, record, offset, start_ns = await asyncio.wait_for(q.get(), timeout=0.1)
                try:
                    output_records = await loop.run_in_executor(
                        self._pool, _run_operator_sync, op, record
                    )
                    await self._emit(operator_id, output_records)
                    latency_ms = (time.monotonic_ns() - start_ns) / 1e6
                    self._metrics.record_latency(operator_id, latency_ms)
                except Exception as e:
                    log.error("CPU-bound operator %s error: %s", operator_id, e)
                finally:
                    q.task_done()
            except asyncio.TimeoutError:
                continue

    async def _emit(self, operator_id: str, records: list[dict]) -> None:
        for out_topic in self._output_routes.get(operator_id, []):
            for record in records:
                await self._bridge.send(out_topic, record)

    async def _check_backpressure(self, topic: str) -> None:
        high = self._config.backpressure_high_water
        low = self._config.backpressure_low_water
        for oid in self._topic_bindings.get(topic, []):
            q = self._worker_queues.get(oid)
            if q is None:
                continue
            depth = q.qsize()
            if depth > high and topic not in self._paused_topics:
                self._consumers[topic].pause(self._consumers[topic].assignment())
                self._paused_topics.add(topic)
                log.debug("Backpressure: paused consumer for topic %s (depth=%d)", topic, depth)
            elif depth < low and topic in self._paused_topics:
                self._consumers[topic].resume(self._consumers[topic].assignment())
                self._paused_topics.discard(topic)
                log.debug("Backpressure: resumed consumer for topic %s (depth=%d)", topic, depth)

    @staticmethod
    def _deserialize_record(value: bytes) -> dict:
        import msgpack
        return msgpack.unpackb(value, raw=False)


def _run_operator_sync(operator: BaseOperator, record: dict) -> list[dict]:
    import asyncio
    return asyncio.run(operator.process(record))
