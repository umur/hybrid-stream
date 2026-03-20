package ai.hybridstream.connector.config;

/**
 * Configuration for the HybridStream Flink Connector.
 * Read from environment variables with sensible defaults.
 */
public class ConnectorConfig {

    public int    grpcPort             = intEnv("FLINK_CONNECTOR_GRPC_PORT", 50053);
    public String kafkaBootstrap       = strEnv("KAFKA_BOOTSTRAP",           "localhost:9092");
    public String kafkaGroupPrefix     = strEnv("KAFKA_GROUP_PREFIX",        "flink-connector");
    public String minioEndpoint        = strEnv("MINIO_ENDPOINT",            "http://localhost:9000");
    public String minioAccessKey       = strEnv("MINIO_ACCESS_KEY",          "hybridstream");
    public String minioSecretKey       = strEnv("MINIO_SECRET_KEY",          "hybridstream123");
    public String minioBucket          = strEnv("MINIO_BUCKET",              "hybridstream-snapshots");
    public int    taskManagerSlots     = intEnv("FLINK_TM_SLOTS",            2);
    public int    taskManagerCount     = intEnv("FLINK_TM_COUNT",            4);
    public String rocksdbCheckpointDir = strEnv("FLINK_CHECKPOINT_DIR",      "s3://hybridstream-checkpoints/flink");
    public long   checkpointIntervalMs = longEnv("FLINK_CHECKPOINT_MS",      30_000L);
    public String schemaDir            = strEnv("SCHEMA_DIR",                "/app/schemas");
    public int    snapshotTranslationTimeoutMs = intEnv("SNAPSHOT_TRANSLATION_TIMEOUT_MS", 200);

    public static ConnectorConfig fromEnv() {
        return new ConnectorConfig();
    }

    // ── helpers ──────────────────────────────────────────────────────────────
    private static String strEnv(String key, String def) {
        String v = System.getenv(key);
        return v != null ? v : def;
    }
    private static int intEnv(String key, int def) {
        String v = System.getenv(key);
        return v != null ? Integer.parseInt(v) : def;
    }
    private static long longEnv(String key, long def) {
        String v = System.getenv(key);
        return v != null ? Long.parseLong(v) : def;
    }
}
