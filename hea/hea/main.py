import asyncio
import logging

from .config import HEAConfig
from .metrics import HEAMetrics
from .execution.engine import OperatorEngine
from .kafka.producer import BridgeProducer
from .state.checkpoint import PeriodicCheckpointer
from .grpc.server import serve
from hybridstream.common.schema_registry import SchemaRegistry
from hybridstream.common.object_store import ObjectStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main() -> None:
    config = HEAConfig()
    log.info("Starting HEA node_id=%s", config.node_id)

    schema_registry = SchemaRegistry(local_schema_dir=config.schema_dir)
    object_store = ObjectStore(
        endpoint_url=config.minio_endpoint,
        access_key=config.minio_access_key,
        secret_key=config.minio_secret_key,
        bucket=config.minio_bucket,
    )
    metrics = HEAMetrics(
        alpha=config.ewma_alpha,
        rtt_probe_interval_ms=config.rtt_probe_interval_ms,
        cloud_kafka_endpoint=config.cloud_kafka_endpoint,
    )
    bridge_producer = BridgeProducer(bootstrap_servers=config.kafka_bootstrap)
    engine = OperatorEngine(config, metrics, bridge_producer)
    checkpointer = PeriodicCheckpointer(
        interval_s=config.checkpoint_interval_s,
        checkpoint_base_dir=config.rocksdb_path,
    )

    await bridge_producer.start()
    await engine.start()
    metrics.start()
    checkpointer.start()

    log.info("HEA fully initialized. Waiting for AODE placement directives.")

    await serve(config, engine, metrics, schema_registry, object_store)


if __name__ == "__main__":
    asyncio.run(main())
