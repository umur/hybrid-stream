"""Tests for hea.hea.config — HEAConfig pydantic-settings model."""
import pytest


class TestHEAConfigDefaults:
    """HEAConfig should have correct defaults when no env vars are set."""

    def test_default_node_id(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.node_id == "edge-node-1"

    def test_default_grpc_port(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.grpc_port == 50051

    def test_default_kafka_bootstrap(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.kafka_bootstrap == "localhost:9092"

    def test_default_kafka_batch_size(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.kafka_batch_size == 500

    def test_default_kafka_group_prefix(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.kafka_group_prefix == "hea"

    def test_default_minio_endpoint(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.minio_endpoint == "http://localhost:9000"

    def test_default_minio_bucket(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.minio_bucket == "hybridstream-snapshots"

    def test_default_rocksdb_path(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.rocksdb_path == "/data/rocksdb"

    def test_default_checkpoint_interval(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.checkpoint_interval_s == 30

    def test_default_worker_pool_size(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.worker_pool_size == 3

    def test_default_backpressure_high_water(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.backpressure_high_water == 6

    def test_default_backpressure_low_water(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.backpressure_low_water == 2

    def test_default_rtt_probe_interval(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.rtt_probe_interval_ms == 500

    def test_default_ewma_alpha(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.ewma_alpha == 0.2

    def test_default_cloud_kafka_endpoint(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.cloud_kafka_endpoint == "localhost:9092"

    def test_default_schema_dir(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.schema_dir == "../../schema-registry/schemas"

    def test_default_etcd_endpoints(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.etcd_endpoints == ["localhost:2379"]

    def test_default_minio_access_key(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.minio_access_key == "hybridstream"

    def test_default_minio_secret_key(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.minio_secret_key == "hybridstream123"


class TestHEAConfigFromEnv:
    """HEAConfig should load overrides from environment variables."""

    def test_node_id_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_NODE_ID", "custom-node-42")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.node_id == "custom-node-42"

    def test_grpc_port_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_GRPC_PORT", "60000")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.grpc_port == 60000

    def test_kafka_bootstrap_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_KAFKA_BOOTSTRAP", "kafka.prod:9093")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.kafka_bootstrap == "kafka.prod:9093"

    def test_backpressure_high_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_BACKPRESSURE_HIGH", "10")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.backpressure_high_water == 10

    def test_ewma_alpha_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_EWMA_ALPHA", "0.5")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.ewma_alpha == 0.5

    def test_worker_pool_size_from_env(self, monkeypatch):
        monkeypatch.setenv("HEA_WORKER_POOL_SIZE", "8")
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        assert cfg.worker_pool_size == 8


class TestHEAConfigAllFieldsPresent:
    """Every field from the spec must exist on the config object."""

    EXPECTED_FIELDS = [
        "node_id", "grpc_port",
        "kafka_bootstrap", "kafka_batch_size", "kafka_group_prefix",
        "minio_endpoint", "minio_access_key", "minio_secret_key", "minio_bucket",
        "etcd_endpoints",
        "rocksdb_path", "checkpoint_interval_s",
        "worker_pool_size",
        "backpressure_high_water", "backpressure_low_water",
        "rtt_probe_interval_ms", "ewma_alpha", "cloud_kafka_endpoint",
        "schema_dir",
    ]

    def test_all_fields_exist(self):
        from hea.hea.config import HEAConfig
        cfg = HEAConfig()
        for field in self.EXPECTED_FIELDS:
            assert hasattr(cfg, field), f"Missing field: {field}"
