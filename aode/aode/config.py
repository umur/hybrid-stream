from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class AODEConfig(BaseSettings):
    # Identity
    instance_id:            str   = Field("aode-1",              validation_alias=AliasChoices("AODE_INSTANCE_ID", "instance_id"))
    cluster_id:             str   = Field("default",             validation_alias=AliasChoices("AODE_CLUSTER_ID", "cluster_id"))

    # gRPC
    grpc_port:              int   = Field(50052,                 validation_alias=AliasChoices("AODE_GRPC_PORT", "grpc_port"))

    # etcd
    etcd_endpoints:         list[str] = Field(["localhost:2379"], validation_alias=AliasChoices("AODE_ETCD_ENDPOINTS", "etcd_endpoints"))
    etcd_key_prefix:        str   = Field("/aode/",              validation_alias=AliasChoices("AODE_ETCD_PREFIX", "etcd_key_prefix"))

    # Leader election
    leader_election_ttl:    int   = Field(30,                    validation_alias=AliasChoices("AODE_LEADER_TTL", "leader_election_ttl"))

    # Telemetry
    telemetry_interval_s:   int   = Field(5,                     validation_alias=AliasChoices("AODE_TELEMETRY_INTERVAL", "telemetry_interval_s"))
    telemetry_timeout_s:    int   = Field(2,                     validation_alias=AliasChoices("AODE_TELEMETRY_TIMEOUT", "telemetry_timeout_s"))

    # Recalibration
    recalibration_interval_s: int = Field(5,                     validation_alias=AliasChoices("AODE_RECALIBRATION_INTERVAL", "recalibration_interval_s"))
    recalibration_enabled:  bool  = Field(True,                  validation_alias=AliasChoices("AODE_RECALIBRATION_ENABLED", "recalibration_enabled"))

    # Scoring constants
    kappa:                  float = Field(2.0,                   validation_alias=AliasChoices("AODE_KAPPA", "kappa"))
    delta_h:                float = Field(0.15,                  validation_alias=AliasChoices("AODE_DELTA_H", "delta_h"))
    lookahead_horizon_s:    int   = Field(30,                    validation_alias=AliasChoices("AODE_LOOKAHEAD_HORIZON", "lookahead_horizon_s"))
    slo_penalty_factor:     int   = Field(10,                    validation_alias=AliasChoices("AODE_SLO_PENALTY", "slo_penalty_factor"))

    # Weight preset
    default_weight_preset:  str   = Field("balanced",            validation_alias=AliasChoices("AODE_DEFAULT_WEIGHTS", "default_weight_preset"))

    # HEA discovery
    hea_discovery_method:   str   = Field("static",              validation_alias=AliasChoices("AODE_HEA_DISCOVERY", "hea_discovery_method"))
    hea_endpoints:          list[str] = Field(
        ["edge-node-1:50051", "edge-node-2:50051", "edge-node-3:50051", "edge-node-4:50051"],
        validation_alias=AliasChoices("AODE_HEA_ENDPOINTS", "hea_endpoints"),
    )

    # Flink connector
    flink_connector_endpoint: str = Field("localhost:50053",     validation_alias=AliasChoices("AODE_FLINK_CONNECTOR", "flink_connector_endpoint"))

    # Migration
    migration_timeout_s:    int   = Field(300,                   validation_alias=AliasChoices("AODE_MIGRATION_TIMEOUT", "migration_timeout_s"))
    drain_timeout_s:        int   = Field(60,                    validation_alias=AliasChoices("AODE_DRAIN_TIMEOUT", "drain_timeout_s"))

    # MinIO / Object store
    minio_endpoint:         str   = Field("http://localhost:9000", validation_alias=AliasChoices("AODE_MINIO_ENDPOINT", "minio_endpoint"))
    minio_access_key:       str   = Field("hybridstream",         validation_alias=AliasChoices("AODE_MINIO_ACCESS_KEY", "minio_access_key"))
    minio_secret_key:       str   = Field("hybridstream123",      validation_alias=AliasChoices("AODE_MINIO_SECRET_KEY", "minio_secret_key"))
    minio_bucket:           str   = Field("hybridstream-snapshots", validation_alias=AliasChoices("AODE_MINIO_BUCKET", "minio_bucket"))

    model_config = {"env_file": ".env", "populate_by_name": True}
