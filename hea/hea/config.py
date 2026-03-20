from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class HEAConfig(BaseSettings):
    # Identity
    node_id:                str   = Field("edge-node-1",         validation_alias=AliasChoices("HEA_NODE_ID", "node_id"))

    # gRPC server
    grpc_port:              int   = Field(50051,                  validation_alias=AliasChoices("HEA_GRPC_PORT", "grpc_port"))

    # Kafka
    kafka_bootstrap:        str   = Field("kafka:9092",           validation_alias=AliasChoices("HEA_KAFKA_BOOTSTRAP", "kafka_bootstrap"))
    kafka_batch_size:       int   = Field(500,                    validation_alias=AliasChoices("HEA_KAFKA_BATCH_SIZE", "kafka_batch_size"))
    kafka_group_prefix:     str   = Field("hea",                  validation_alias=AliasChoices("HEA_KAFKA_GROUP_PREFIX", "kafka_group_prefix"))

    # Object store
    minio_endpoint:         str   = Field("http://minio:9000",    validation_alias=AliasChoices("HEA_MINIO_ENDPOINT", "minio_endpoint"))
    minio_access_key:       str   = Field("hybridstream",         validation_alias=AliasChoices("HEA_MINIO_ACCESS_KEY", "minio_access_key"))
    minio_secret_key:       str   = Field("hybridstream123",      validation_alias=AliasChoices("HEA_MINIO_SECRET_KEY", "minio_secret_key"))
    minio_bucket:           str   = Field("hybridstream-snapshots", validation_alias=AliasChoices("HEA_MINIO_BUCKET", "minio_bucket"))

    # etcd
    etcd_endpoints:         list[str] = Field(["http://etcd:2379"], validation_alias=AliasChoices("HEA_ETCD_ENDPOINTS", "etcd_endpoints"))

    # State
    rocksdb_path:           str   = Field("/data/rocksdb",        validation_alias=AliasChoices("HEA_ROCKSDB_PATH", "rocksdb_path"))
    checkpoint_interval_s:  int   = Field(30,                     validation_alias=AliasChoices("HEA_CHECKPOINT_INTERVAL_S", "checkpoint_interval_s"))

    # Execution
    worker_pool_size:       int   = Field(3,                      validation_alias=AliasChoices("HEA_WORKER_POOL_SIZE", "worker_pool_size"))

    # Backpressure
    backpressure_high_water: int  = Field(6,                      validation_alias=AliasChoices("HEA_BACKPRESSURE_HIGH", "backpressure_high_water"))
    backpressure_low_water:  int  = Field(2,                      validation_alias=AliasChoices("HEA_BACKPRESSURE_LOW", "backpressure_low_water"))

    # Metrics
    rtt_probe_interval_ms:  int   = Field(500,                    validation_alias=AliasChoices("HEA_RTT_PROBE_MS", "rtt_probe_interval_ms"))
    ewma_alpha:             float = Field(0.2,                    validation_alias=AliasChoices("HEA_EWMA_ALPHA", "ewma_alpha"))
    cloud_kafka_endpoint:   str   = Field("localhost:9092",       validation_alias=AliasChoices("HEA_CLOUD_KAFKA_ENDPOINT", "cloud_kafka_endpoint"))

    # Schema registry
    schema_dir:             str   = Field("../../schema-registry/schemas", validation_alias=AliasChoices("HEA_SCHEMA_DIR", "schema_dir"))

    model_config = {"env_file": ".env", "populate_by_name": True}
