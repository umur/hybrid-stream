import asyncio
import logging
import signal

from .config import AODEConfig
from .etcd.client import EtcdClient
from .grpc.clients import HEAClient, FlinkConnectorClient
from .grpc.server import serve_management_api
from .placement.state import PlacementState
from .placement.optimizer import PlacementOptimizer
from .scoring.algorithm import ScoringAlgorithm
from .migration.pctr import PCTROrchestrator
from .telemetry.collector import TelemetryCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def run() -> None:
    config = AODEConfig()
    log.info("AODE starting — instance_id=%s  port=%s", config.instance_id, config.grpc_port)

    # 1. Infrastructure clients
    etcd_client  = EtcdClient(config.etcd_endpoints, config.etcd_key_prefix)
    hea_clients  = {ep: HEAClient(ep) for ep in config.hea_endpoints}
    flink_client = FlinkConnectorClient(config.flink_connector_endpoint)

    for client in hea_clients.values():
        await client.connect()
    await flink_client.connect()

    # 2. Core components (in dependency order)
    telemetry       = TelemetryCollector(config)
    scoring         = ScoringAlgorithm(config, telemetry)
    placement_state = PlacementState(etcd_client)
    migration_orch  = PCTROrchestrator(config, hea_clients, flink_client, object_store=None)
    optimizer       = PlacementOptimizer(
        config                 = config,
        scoring                = scoring,
        migration_orchestrator = migration_orch,
        placement_state        = placement_state,
    )

    # Wire HEA clients into the telemetry collector's stub resolution
    # _get_stub(hea_id) where hea_id is "hea-node-1" — map from hostname to client stub
    _ep_map = {ep.split(":")[0]: client for ep, client in hea_clients.items()}
    _ep_map.update({ep: client for ep, client in hea_clients.items()})  # also full endpoint

    class _StubAdapter:
        """Adapter so TelemetryCollector can call CollectTelemetry via HEAClient.get_telemetry"""
        def __init__(self, client):
            self._client = client
        async def CollectTelemetry(self):
            return await self._client.get_telemetry()

    def _patched_get_stub(hea_id):
        client = _ep_map.get(hea_id)
        return _StubAdapter(client) if client else None

    telemetry._get_stub = _patched_get_stub

    # 3. Start components
    await telemetry.start()
    await optimizer.start()

    # 4. Background tasks
    loop     = asyncio.get_running_loop()
    tel_task = loop.create_task(telemetry._collection_loop())
    opt_task = loop.create_task(optimizer._optimization_loop())

    # 5. Graceful shutdown
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    # 6. Start gRPC server
    grpc_task = loop.create_task(
        serve_management_api(config.grpc_port, optimizer, placement_state, migration_orch, scoring)
    )

    log.info("AODE gRPC server listening on port %s", config.grpc_port)
    await stop.wait()

    log.info("AODE shutting down…")
    await telemetry.stop()
    await optimizer.stop()
    for task in (grpc_task, tel_task, opt_task):
        task.cancel()
    await asyncio.gather(grpc_task, tel_task, opt_task, return_exceptions=True)

    for client in hea_clients.values():
        await client.close()
    await flink_client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
