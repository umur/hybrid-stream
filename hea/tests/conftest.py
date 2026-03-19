import pytest


@pytest.fixture
def hea_env(monkeypatch):
    """Set minimal env vars for HEAConfig instantiation."""
    monkeypatch.setenv("HEA_NODE_ID", "test-node-1")
    monkeypatch.setenv("HEA_GRPC_PORT", "50099")
    monkeypatch.setenv("HEA_KAFKA_BOOTSTRAP", "localhost:9092")
    monkeypatch.setenv("HEA_MINIO_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("HEA_MINIO_ACCESS_KEY", "testkey")
    monkeypatch.setenv("HEA_MINIO_SECRET_KEY", "testsecret")
    monkeypatch.setenv("HEA_MINIO_BUCKET", "test-bucket")
    monkeypatch.setenv("HEA_ROCKSDB_PATH", "/tmp/test-rocksdb")
