package ai.hybridstream.connector;

import ai.hybridstream.connector.config.ConnectorConfig;
import ai.hybridstream.connector.grpc.FlinkConnectorServiceImpl;
import ai.hybridstream.connector.snapshot.SchemaRegistry;
import ai.hybridstream.connector.store.MinIOClient;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * HybridStream Flink Connector entrypoint.
 * Starts the gRPC management server and waits for AODE commands.
 */
public class HybridStreamConnector {

    private static final Logger log = LoggerFactory.getLogger(HybridStreamConnector.class);

    public static void main(String[] args) throws Exception {
        ConnectorConfig config = ConnectorConfig.fromEnv();

        // Initialize schema registry
        SchemaRegistry schemaRegistry = new SchemaRegistry();
        schemaRegistry.loadFromDirectory(config.schemaDir);

        // Initialize MinIO client
        MinIOClient minioClient = new MinIOClient(
            config.minioEndpoint,
            config.minioAccessKey,
            config.minioSecretKey,
            config.minioBucket
        );

        // Build gRPC server
        FlinkConnectorServiceImpl service = new FlinkConnectorServiceImpl(config, minioClient, schemaRegistry);

        Server server = ServerBuilder
            .forPort(config.grpcPort)
            .addService(service)
            .build();

        server.start();
        log.info("HybridStream Flink Connector started on port {}", config.grpcPort);

        // Shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down Flink Connector gRPC server");
            server.shutdown();
        }));

        server.awaitTermination();
    }
}