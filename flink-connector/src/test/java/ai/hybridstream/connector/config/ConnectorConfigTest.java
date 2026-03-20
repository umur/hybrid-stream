package ai.hybridstream.connector.config;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConnectorConfigTest {

    @Test
    void testDefaultGrpcPort() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals(50053, config.grpcPort);
    }

    @Test
    void testDefaultKafkaBootstrap() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("localhost:9092", config.kafkaBootstrap);
    }

    @Test
    void testDefaultKafkaGroupPrefix() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("flink-connector", config.kafkaGroupPrefix);
    }

    @Test
    void testDefaultMinioEndpoint() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("http://localhost:9000", config.minioEndpoint);
    }

    @Test
    void testDefaultMinioAccessKey() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("hybridstream", config.minioAccessKey);
    }

    @Test
    void testDefaultMinioSecretKey() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("hybridstream123", config.minioSecretKey);
    }

    @Test
    void testDefaultMinioBucket() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("hybridstream-snapshots", config.minioBucket);
    }

    @Test
    void testDefaultTaskManagerSlots() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals(2, config.taskManagerSlots);
    }

    @Test
    void testDefaultTaskManagerCount() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals(4, config.taskManagerCount);
    }

    @Test
    void testDefaultRocksdbCheckpointDir() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("s3://hybridstream-checkpoints/flink", config.rocksdbCheckpointDir);
    }

    @Test
    void testDefaultCheckpointIntervalMs() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals(30_000L, config.checkpointIntervalMs);
    }

    @Test
    void testDefaultSchemaDir() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals("/app/schemas", config.schemaDir);
    }

    @Test
    void testDefaultSnapshotTranslationTimeoutMs() {
        ConnectorConfig config = ConnectorConfig.fromEnv();
        assertEquals(200, config.snapshotTranslationTimeoutMs);
    }
}