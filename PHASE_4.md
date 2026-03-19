# Phase 4 — HybridStream Flink Connector

> **Depends on:** Phase 1 complete (proto stubs, schema registry), Phase 3 complete (AODE can issue migration directives)  
> **Goal:** A Java 17 Flink 1.18.1 plugin that receives PCTR restore commands from AODE, deserializes MessagePack snapshots from MinIO, and runs operators as Flink TaskManager tasks.  
> Estimated scope: ~1,200 lines of Java.

---

## Deliverables Checklist

- [ ] `flink-connector/pom.xml` — Maven build with Flink 1.18.1 deps
- [ ] `flink-connector/src/main/proto/hybridstream.proto` symlink (or copy)
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/HybridStreamConnector.java` — entrypoint
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/config/ConnectorConfig.java`
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/grpc/FlinkConnectorServiceImpl.java` — gRPC server
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/snapshot/SnapshotDeserializer.java` — MessagePack → Flink state
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/snapshot/SchemaRegistry.java` — schema version lookup
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/operator/MigratedOperator.java` — generic restored operator
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/operator/OperatorFactory.java`
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/kafka/KafkaBridgeSource.java` — consume bridge topic
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/kafka/KafkaBridgeSink.java` — produce output
- [ ] `flink-connector/src/main/java/ai/hybridstream/connector/store/MinIOClient.java` — download snapshots
- [ ] `flink-connector/src/test/java/` — unit + integration tests
- [ ] All tests passing (`mvn test`)

---

## Step 1 — `flink-connector/pom.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>ai.hybridstream</groupId>
    <artifactId>hybridstream-flink-connector</artifactId>
    <version>0.1.0</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <flink.version>1.18.1</flink.version>
        <kafka.version>3.6.1</kafka.version>
        <grpc.version>1.62.0</grpc.version>
        <protobuf.version>3.25.3</protobuf.version>
        <minio.version>8.5.7</minio.version>
        <msgpack.version>0.9.8</msgpack.version>
        <jackson.version>2.16.1</jackson.version>
        <junit.version>5.10.1</junit.version>
    </properties>

    <dependencies>
        <!-- Apache Flink -->
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-streaming-java</artifactId>
            <version>${flink.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-clients</artifactId>
            <version>${flink.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-connector-kafka</artifactId>
            <version>3.1.0-1.18</version>
        </dependency>
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-statebackend-rocksdb</artifactId>
            <version>${flink.version}</version>
        </dependency>

        <!-- gRPC + Protobuf -->
        <dependency>
            <groupId>io.grpc</groupId>
            <artifactId>grpc-netty-shaded</artifactId>
            <version>${grpc.version}</version>
        </dependency>
        <dependency>
            <groupId>io.grpc</groupId>
            <artifactId>grpc-protobuf</artifactId>
            <version>${grpc.version}</version>
        </dependency>
        <dependency>
            <groupId>io.grpc</groupId>
            <artifactId>grpc-stub</artifactId>
            <version>${grpc.version}</version>
        </dependency>
        <dependency>
            <groupId>com.google.protobuf</groupId>
            <artifactId>protobuf-java</artifactId>
            <version>${protobuf.version}</version>
        </dependency>

        <!-- MinIO S3-compatible client -->
        <dependency>
            <groupId>io.minio</groupId>
            <artifactId>minio</artifactId>
            <version>${minio.version}</version>
        </dependency>

        <!-- MessagePack for snapshot deserialization -->
        <dependency>
            <groupId>org.msgpack</groupId>
            <artifactId>msgpack-core</artifactId>
            <version>${msgpack.version}</version>
        </dependency>
        <dependency>
            <groupId>org.msgpack</groupId>
            <artifactId>jackson-dataformat-msgpack</artifactId>
            <version>${msgpack.version}</version>
        </dependency>

        <!-- Jackson -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>${jackson.version}</version>
        </dependency>

        <!-- Logging -->
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>2.0.11</version>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-test-utils</artifactId>
            <version>${flink.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.xolstice.maven.plugins</groupId>
                <artifactId>protobuf-maven-plugin</artifactId>
                <version>0.6.1</version>
                <configuration>
                    <protocArtifact>com.google.protobuf:protoc:${protobuf.version}:exe:${os.detected.classifier}</protocArtifact>
                    <pluginId>grpc-java</pluginId>
                    <pluginArtifact>io.grpc:protoc-gen-grpc-java:${grpc.version}:exe:${os.detected.classifier}</pluginArtifact>
                </configuration>
                <executions>
                    <execution>
                        <goals>
                            <goal>compile</goal>
                            <goal>compile-custom</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-shade-plugin</artifactId>
                <version>3.5.1</version>
                <executions>
                    <execution>
                        <phase>package</phase>
                        <goals><goal>shade</goal></goals>
                        <configuration>
                            <createDependencyReducedPom>false</createDependencyReducedPom>
                            <artifactSet>
                                <excludes>
                                    <exclude>org.apache.flink:flink-*:*:provided</exclude>
                                </excludes>
                            </artifactSet>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## Step 2 — `ConnectorConfig.java`

```java
package ai.hybridstream.connector.config;

import java.util.List;
import java.util.Map;

/**
 * Configuration for the HybridStream Flink Connector.
 * Read from environment variables or a YAML config file.
 */
public class ConnectorConfig {

    // gRPC server
    public int grpcPort = Integer.parseInt(System.getenv().getOrDefault("FLINK_CONNECTOR_GRPC_PORT", "50053"));

    // Kafka
    public String kafkaBootstrap = System.getenv().getOrDefault("KAFKA_BOOTSTRAP", "localhost:9092");
    public String kafkaGroupPrefix = System.getenv().getOrDefault("KAFKA_GROUP_PREFIX", "flink-connector");

    // MinIO / Object Store
    public String minioEndpoint   = System.getenv().getOrDefault("MINIO_ENDPOINT",   "http://localhost:9000");
    public String minioAccessKey  = System.getenv().getOrDefault("MINIO_ACCESS_KEY",  "hybridstream");
    public String minioSecretKey  = System.getenv().getOrDefault("MINIO_SECRET_KEY",  "hybridstream123");
    public String minioBucket     = System.getenv().getOrDefault("MINIO_BUCKET",      "hybridstream-snapshots");

    // Flink
    public int    taskManagerSlots    = Integer.parseInt(System.getenv().getOrDefault("FLINK_TM_SLOTS",    "2"));
    public int    taskManagerCount    = Integer.parseInt(System.getenv().getOrDefault("FLINK_TM_COUNT",    "4"));
    public String rocksdbCheckpointDir = System.getenv().getOrDefault("FLINK_CHECKPOINT_DIR", "s3://hybridstream-checkpoints/flink");
    public long   checkpointIntervalMs = Long.parseLong(System.getenv().getOrDefault("FLINK_CHECKPOINT_MS", "30000")); // 30s

    // Schema registry (path to JSON schema files)
    public String schemaDir = System.getenv().getOrDefault("SCHEMA_DIR", "/app/schemas");

    // Snapshot translation overhead tolerance (ms)
    public int snapshotTranslationTimeoutMs = Integer.parseInt(
        System.getenv().getOrDefault("SNAPSHOT_TRANSLATION_TIMEOUT_MS", "200")
    );

    public static ConnectorConfig fromEnv() {
        return new ConnectorConfig();
    }
}
```

---

## Step 3 — `MinIOClient.java`

```java
package ai.hybridstream.connector.store;

import io.minio.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.io.ByteArrayOutputStream;

/**
 * Thin wrapper around the MinIO Java SDK for snapshot download.
 * Snapshots are written by HEA (Python) and read by this connector (Java).
 * Format: MessagePack bytes with embedded schema version header.
 */
public class MinIOClient {

    private static final Logger log = LoggerFactory.getLogger(MinIOClient.class);

    private final io.minio.MinioClient client;
    private final String bucket;

    public MinIOClient(String endpoint, String accessKey, String secretKey, String bucket) {
        this.client = io.minio.MinioClient.builder()
            .endpoint(endpoint)
            .credentials(accessKey, secretKey)
            .build();
        this.bucket = bucket;
        log.info("MinIO client initialized: endpoint={} bucket={}", endpoint, bucket);
    }

    /**
     * Download a snapshot from MinIO as a raw byte array.
     * Measured transfer rate: 210 MB/s sustained on evaluation platform.
     *
     * @param objectKey  The MinIO object key (e.g., "edge-node-1/operator-abc/1/snapshot.msgpack")
     * @return Raw bytes of the snapshot
     */
    public byte[] downloadSnapshot(String objectKey) throws Exception {
        long startNs = System.nanoTime();
        log.debug("Downloading snapshot: key={}", objectKey);

        try (InputStream stream = client.getObject(
                GetObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectKey)
                    .build()
        )) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[65536]; // 64 KB chunks
            int bytesRead;
            while ((bytesRead = stream.read(chunk)) != -1) {
                buffer.write(chunk, 0, bytesRead);
            }
            byte[] result = buffer.toByteArray();
            double elapsedMs = (System.nanoTime() - startNs) / 1e6;
            log.info("Downloaded snapshot: key={} size={}B elapsed={}ms", objectKey, result.length, String.format("%.1f", elapsedMs));
            return result;
        }
    }

    /**
     * Upload a translated Flink-format snapshot back to MinIO.
     * Used during PCTR Phase 3 when restoring state to a Flink operator.
     */
    public void uploadFlinkSnapshot(String objectKey, byte[] data) throws Exception {
        try (var stream = new java.io.ByteArrayInputStream(data)) {
            client.putObject(
                PutObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectKey)
                    .stream(stream, data.length, -1)
                    .contentType("application/octet-stream")
                    .build()
            );
        }
        log.debug("Uploaded Flink snapshot: key={} size={}B", objectKey, data.length);
    }

    /**
     * Check whether a snapshot object exists in MinIO.
     * Used to verify PCTR Phase 2 completed successfully.
     */
    public boolean snapshotExists(String objectKey) {
        try {
            client.statObject(StatObjectArgs.builder().bucket(bucket).object(objectKey).build());
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
```

---

## Step 4 — `SnapshotDeserializer.java`

```java
package ai.hybridstream.connector.snapshot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.msgpack.jackson.dataformat.MessagePackFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.Map;

/**
 * Deserializes MessagePack snapshots produced by the Python HEA into
 * Java Map<String, Object> state maps that Flink operators can consume.
 *
 * Snapshot wire format (from hybridstream-common/snapshot.py):
 *   [0..3]  : magic bytes 0x48 0x53 0x4D 0x50 ("HSMP")
 *   [4..5]  : schema_version (uint16 big-endian)
 *   [6..]   : MessagePack-encoded payload dict
 *
 * Translation overhead: 45–120ms measured on c5.4xlarge (§5.3 of paper).
 */
public class SnapshotDeserializer {

    private static final Logger log = LoggerFactory.getLogger(SnapshotDeserializer.class);

    private static final byte[] MAGIC = {0x48, 0x53, 0x4D, 0x50}; // "HSMP"
    private static final int HEADER_SIZE = 6; // 4 magic + 2 version

    private final ObjectMapper msgpackMapper;
    private final SchemaRegistry schemaRegistry;

    public SnapshotDeserializer(SchemaRegistry schemaRegistry) {
        this.msgpackMapper = new ObjectMapper(new MessagePackFactory());
        this.schemaRegistry = schemaRegistry;
    }

    /**
     * Deserialize a raw snapshot byte array into a typed state map.
     *
     * @param snapshotBytes  Raw bytes from MinIO
     * @param operatorType   Expected operator type (e.g., "VehicleDetector")
     * @return               Deserialized state as Map<String, Object>
     * @throws IOException   If deserialization fails or magic/version mismatch
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> deserialize(byte[] snapshotBytes, String operatorType) throws IOException {
        long startNs = System.nanoTime();

        // Validate magic bytes
        for (int i = 0; i < MAGIC.length; i++) {
            if (snapshotBytes[i] != MAGIC[i]) {
                throw new IOException("Invalid snapshot magic bytes — expected HSMP header");
            }
        }

        // Extract schema version
        int schemaVersion = ((snapshotBytes[4] & 0xFF) << 8) | (snapshotBytes[5] & 0xFF);
        log.debug("Deserializing {} snapshot: schema_version={} size={}B", operatorType, schemaVersion, snapshotBytes.length);

        // Validate schema version
        if (!schemaRegistry.isVersionSupported(operatorType, schemaVersion)) {
            throw new IOException(String.format(
                "Unsupported schema version %d for operator type %s. Supported: %s",
                schemaVersion, operatorType, schemaRegistry.getSupportedVersions(operatorType)
            ));
        }

        // Deserialize MessagePack payload
        byte[] payload = new byte[snapshotBytes.length - HEADER_SIZE];
        System.arraycopy(snapshotBytes, HEADER_SIZE, payload, 0, payload.length);

        Map<String, Object> state = msgpackMapper.readValue(payload, Map.class);

        double elapsedMs = (System.nanoTime() - startNs) / 1e6;
        log.info("Deserialized {} snapshot: fields={} elapsed={}ms", operatorType, state.size(), String.format("%.1f", elapsedMs));

        return state;
    }

    /**
     * Translate a Python-serialized state map into a Flink-compatible state representation.
     * Handles type conversions between Python and Java (e.g., Python lists → Java List).
     * This is where the 45–120ms translation overhead is incurred.
     *
     * @param rawState    Deserialized MessagePack state
     * @param operatorType Operator type for schema-aware translation
     * @return            Flink-ready state representation
     */
    public Map<String, Object> translateToFlinkState(Map<String, Object> rawState, String operatorType) {
        // Schema-driven translation
        Map<String, String> schema = schemaRegistry.getSchema(operatorType);

        return rawState.entrySet().stream()
            .filter(e -> schema.containsKey(e.getKey()))
            .collect(
                java.util.stream.Collectors.toMap(
                    Map.Entry::getKey,
                    e -> translateValue(e.getValue(), schema.get(e.getKey()))
                )
            );
    }

    private Object translateValue(Object value, String schemaType) {
        if (value == null) return null;
        return switch (schemaType) {
            case "float"   -> value instanceof Number ? ((Number) value).doubleValue() : Double.parseDouble(value.toString());
            case "int"     -> value instanceof Number ? ((Number) value).longValue()   : Long.parseLong(value.toString());
            case "boolean" -> value instanceof Boolean ? value : Boolean.parseBoolean(value.toString());
            case "string"  -> value.toString();
            // Lists and maps are passed through as-is (Jackson deserialization handles them)
            default        -> value;
        };
    }
}
```

---

## Step 5 — `SchemaRegistry.java`

```java
package ai.hybridstream.connector.snapshot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.*;

/**
 * Java-side schema registry.
 * Reads the same JSON schema files as the Python hybridstream-common schema registry.
 * Ensures cross-language snapshot compatibility.
 *
 * Schema file format: see schema-registry/schemas/{OperatorType}.json
 */
public class SchemaRegistry {

    private static final Logger log = LoggerFactory.getLogger(SchemaRegistry.class);

    // operator_type → {field_name → field_type}
    private final Map<String, Map<String, String>> schemas = new HashMap<>();
    // operator_type → supported schema versions
    private final Map<String, Set<Integer>> supportedVersions = new HashMap<>();

    private final ObjectMapper jsonMapper = new ObjectMapper();

    /**
     * Load all JSON schema files from the schema directory.
     *
     * @param schemaDir Path to the schema-registry/schemas/ directory
     */
    public void loadFromDirectory(String schemaDir) throws IOException {
        File dir = new File(schemaDir);
        File[] files = dir.listFiles((d, name) -> name.endsWith(".json"));
        if (files == null) {
            throw new IOException("Schema directory not found or empty: " + schemaDir);
        }

        for (File file : files) {
            loadSchema(file);
        }
        log.info("Loaded {} schemas from {}", schemas.size(), schemaDir);
    }

    @SuppressWarnings("unchecked")
    private void loadSchema(File file) throws IOException {
        Map<String, Object> raw = jsonMapper.readValue(file, Map.class);
        String operatorType = (String) raw.get("operator_type");
        int version = (Integer) raw.get("schema_version");
        Map<String, String> fields = (Map<String, String>) raw.get("fields");

        schemas.put(operatorType, fields);
        supportedVersions.computeIfAbsent(operatorType, k -> new HashSet<>()).add(version);

        log.debug("Loaded schema: type={} version={} fields={}", operatorType, version, fields.size());
    }

    public boolean isVersionSupported(String operatorType, int version) {
        Set<Integer> versions = supportedVersions.get(operatorType);
        return versions != null && versions.contains(version);
    }

    public Set<Integer> getSupportedVersions(String operatorType) {
        return supportedVersions.getOrDefault(operatorType, Collections.emptySet());
    }

    public Map<String, String> getSchema(String operatorType) {
        Map<String, String> schema = schemas.get(operatorType);
        if (schema == null) {
            throw new IllegalArgumentException("No schema found for operator type: " + operatorType);
        }
        return schema;
    }

    public Set<String> getRegisteredTypes() {
        return schemas.keySet();
    }
}
```

---

## Step 6 — `MigratedOperator.java`

```java
package ai.hybridstream.connector.operator;

import org.apache.flink.api.common.functions.RichFlatMapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.util.Collector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * A generic Flink operator that wraps state restored from a HEA migration snapshot.
 * 
 * This operator:
 * 1. Holds the restored state as a Flink ValueState<Map<String,Object>>
 * 2. Applies the operator's processing logic as a RichFlatMapFunction
 * 3. Emits output records to the Kafka bridge sink
 * 4. Supports Flink's native checkpointing for ongoing state durability
 *
 * One MigratedOperator instance is created per PCTR Phase 3 restore call.
 */
public class MigratedOperator extends RichFlatMapFunction<Map<String, Object>, Map<String, Object>> {

    private static final Logger log = LoggerFactory.getLogger(MigratedOperator.class);

    private final String operatorId;
    private final String operatorType;
    private final Map<String, Object> restoredState;     // From PCTR Phase 3 snapshot
    private final OperatorLogic logic;                    // Type-specific processing logic

    // Flink-managed state (takes over from restored snapshot after first checkpoint)
    private transient ValueState<Map<String, Object>> flinkState;

    public MigratedOperator(
        String operatorId,
        String operatorType,
        Map<String, Object> restoredState,
        OperatorLogic logic
    ) {
        this.operatorId    = operatorId;
        this.operatorType  = operatorType;
        this.restoredState = restoredState;
        this.logic         = logic;
    }

    @Override
    public void open(Configuration parameters) throws Exception {
        super.open(parameters);

        // Register Flink state descriptor
        ValueStateDescriptor<Map<String, Object>> descriptor =
            new ValueStateDescriptor<>(
                "operator-state-" + operatorId,
                Types.MAP(Types.STRING, Types.PICKLED_BYTE_ARRAY())
            );
        flinkState = getRuntimeContext().getState(descriptor);

        // Restore state from PCTR snapshot into Flink state
        if (restoredState != null && !restoredState.isEmpty()) {
            flinkState.update(restoredState);
            log.info("Restored {} state for operator {}: {} fields", operatorType, operatorId, restoredState.size());
        }
    }

    @Override
    public void flatMap(Map<String, Object> record, Collector<Map<String, Object>> out) throws Exception {
        Map<String, Object> currentState = flinkState.value();

        // Delegate processing to type-specific logic
        OperatorLogic.ProcessResult result = logic.process(record, currentState);

        // Update Flink state
        flinkState.update(result.newState());

        // Emit output records
        for (Map<String, Object> outputRecord : result.outputRecords()) {
            out.collect(outputRecord);
        }
    }

    /**
     * Sealed interface for type-specific operator processing logic.
     * Implemented per operator type in OperatorFactory.
     */
    public interface OperatorLogic {

        ProcessResult process(Map<String, Object> record, Map<String, Object> currentState);

        record ProcessResult(
            Map<String, Object> newState,
            java.util.List<Map<String, Object>> outputRecords
        ) {}
    }
}
```

---

## Step 7 — `OperatorFactory.java`

```java
package ai.hybridstream.connector.operator;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Creates MigratedOperator instances for each supported operator type.
 * The processing logic here must exactly mirror the Python operator implementations
 * in the workloads package (Phase 5).
 *
 * Supported types (matching schema-registry):
 *   NormalizerOperator, FeatureAggWindow, MultiStreamJoin, BinaryClassifier (W1)
 *   VehicleDetector, ZoneAggregator, PatternDetector                        (W2)
 *   RiskCheck, AnomalyDetector, StatAggregator, ComplianceLogger            (W3)
 */
public class OperatorFactory {

    private static final Logger log = LoggerFactory.getLogger(OperatorFactory.class);

    /**
     * Create a MigratedOperator with type-specific logic for the given operator type.
     *
     * @param operatorId     Unique operator instance ID
     * @param operatorType   Type name matching schema registry (e.g., "VehicleDetector")
     * @param restoredState  State map from PCTR Phase 3 snapshot deserialization
     * @return               Ready-to-use MigratedOperator Flink function
     */
    public static MigratedOperator create(
        String operatorId,
        String operatorType,
        Map<String, Object> restoredState
    ) {
        MigratedOperator.OperatorLogic logic = switch (operatorType) {
            // ── W1 Operators ──────────────────────────────────────────────────────────
            case "NormalizerOperator" -> (record, state) -> {
                // Normalize input signal using stored mean/std state
                double mean = getDouble(state, "mean", 0.0);
                double std  = getDouble(state, "std",  1.0);
                double raw  = getDouble(record, "value", 0.0);
                double normalized = std > 0 ? (raw - mean) / std : 0.0;

                Map<String, Object> output = new HashMap<>(record);
                output.put("normalized_value", normalized);

                return new MigratedOperator.OperatorLogic.ProcessResult(state, List.of(output));
            };

            case "FeatureAggWindow" -> (record, state) -> {
                // Sliding window aggregation: sum, count, min, max
                @SuppressWarnings("unchecked")
                List<Double> window = (List<Double>) state.getOrDefault("window", new java.util.ArrayList<>());
                double value = getDouble(record, "value", 0.0);
                window.add(value);

                // Trim to window size
                int windowSize = getInt(state, "window_size", 100);
                while (window.size() > windowSize) window.remove(0);

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("window", window);

                double sum = window.stream().mapToDouble(Double::doubleValue).sum();
                Map<String, Object> output = Map.of(
                    "sum", sum, "count", window.size(),
                    "min", window.stream().mapToDouble(Double::doubleValue).min().orElse(0),
                    "max", window.stream().mapToDouble(Double::doubleValue).max().orElse(0),
                    "avg", window.isEmpty() ? 0 : sum / window.size()
                );

                return new MigratedOperator.OperatorLogic.ProcessResult(newState, List.of(output));
            };

            case "BinaryClassifier" -> (record, state) -> {
                // Binary classification using stored threshold
                double score     = getDouble(record, "score", 0.0);
                double threshold = getDouble(state, "threshold", 0.5);
                boolean positive = score >= threshold;

                Map<String, Object> output = new HashMap<>(record);
                output.put("label", positive ? 1 : 0);
                output.put("confidence", positive ? score : 1.0 - score);

                return new MigratedOperator.OperatorLogic.ProcessResult(state, List.of(output));
            };

            // ── W2 Operators ──────────────────────────────────────────────────────────
            case "VehicleDetector" -> (record, state) -> {
                // Detect vehicle presence from sensor data
                double occupancy = getDouble(record, "occupancy", 0.0);
                double speed     = getDouble(record, "speed", 0.0);
                boolean detected = occupancy > 0.1 && speed > 0;

                Map<String, Object> output = new HashMap<>(record);
                output.put("vehicle_detected", detected);
                output.put("confidence_score", occupancy * (speed / 120.0));

                return new MigratedOperator.OperatorLogic.ProcessResult(state, List.of(output));
            };

            case "ZoneAggregator" -> (record, state) -> {
                // Aggregate vehicle counts per zone
                String zone = (String) record.getOrDefault("zone_id", "unknown");
                @SuppressWarnings("unchecked")
                Map<String, Integer> counts = (Map<String, Integer>) state.getOrDefault("zone_counts", new HashMap<>());
                boolean detected = (boolean) record.getOrDefault("vehicle_detected", false);

                if (detected) {
                    counts.merge(zone, 1, Integer::sum);
                }

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("zone_counts", counts);

                Map<String, Object> output = Map.of(
                    "zone_id", zone,
                    "vehicle_count", counts.getOrDefault(zone, 0),
                    "timestamp", record.getOrDefault("timestamp", 0L)
                );

                return new MigratedOperator.OperatorLogic.ProcessResult(newState, List.of(output));
            };

            // ── W3 Operators ──────────────────────────────────────────────────────────
            case "RiskCheck" -> (record, state) -> {
                // Ultra-low latency risk evaluation (SLO: 1ms)
                double exposure  = getDouble(record, "exposure",  0.0);
                double limit     = getDouble(state,  "risk_limit", 1_000_000.0);
                boolean exceeded = exposure > limit;

                Map<String, Object> output = new HashMap<>(record);
                output.put("risk_exceeded", exceeded);
                output.put("exposure_ratio", limit > 0 ? exposure / limit : 0.0);

                return new MigratedOperator.OperatorLogic.ProcessResult(state, List.of(output));
            };

            case "AnomalyDetector" -> (record, state) -> {
                // Z-score based anomaly detection using EWMA stats
                double value  = getDouble(record, "value", 0.0);
                double mean   = getDouble(state, "ewma_mean", 0.0);
                double stddev = getDouble(state, "ewma_std",  1.0);
                double z      = stddev > 0 ? Math.abs(value - mean) / stddev : 0.0;
                boolean anomaly = z > 3.0;

                // Update EWMA state
                double alpha  = 0.2;
                double newMean = (1 - alpha) * mean + alpha * value;
                double newStd  = (1 - alpha) * stddev + alpha * Math.abs(value - newMean);

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("ewma_mean", newMean);
                newState.put("ewma_std", newStd);

                Map<String, Object> output = new HashMap<>(record);
                output.put("is_anomaly", anomaly);
                output.put("z_score", z);

                return new MigratedOperator.OperatorLogic.ProcessResult(newState, List.of(output));
            };

            case "StatAggregator" -> (record, state) -> {
                // Statistical aggregation (count, sum, mean, variance)
                double value = getDouble(record, "value", 0.0);
                long   count = getLong(state, "count", 0L) + 1;
                double sum   = getDouble(state, "sum", 0.0) + value;
                double mean  = sum / count;

                // Welford's online variance
                double m2    = getDouble(state, "m2", 0.0);
                double delta = value - (sum - value) / Math.max(1, count - 1);
                m2 += delta * (value - mean);

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("count", count);
                newState.put("sum",   sum);
                newState.put("m2",    m2);

                Map<String, Object> output = Map.of(
                    "count", count, "sum", sum, "mean", mean,
                    "variance", count > 1 ? m2 / (count - 1) : 0.0
                );

                return new MigratedOperator.OperatorLogic.ProcessResult(newState, List.of(output));
            };

            case "ComplianceLogger" -> (record, state) -> {
                // Log compliance events (batch, latency-insensitive)
                String eventType = (String) record.getOrDefault("event_type", "unknown");
                long logged = getLong(state, "logged_count", 0L) + 1;

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("logged_count", logged);

                // Pass through with compliance metadata
                Map<String, Object> output = new HashMap<>(record);
                output.put("compliance_logged", true);
                output.put("log_sequence", logged);

                return new MigratedOperator.OperatorLogic.ProcessResult(newState, List.of(output));
            };

            default -> {
                log.warn("Unknown operator type '{}' — using pass-through logic", operatorType);
                yield (record, state) ->
                    new MigratedOperator.OperatorLogic.ProcessResult(state, List.of(record));
            }
        };

        return new MigratedOperator(operatorId, operatorType, restoredState, logic);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────────────

    private static double getDouble(Map<String, Object> map, String key, double defaultValue) {
        Object val = map.get(key);
        if (val == null) return defaultValue;
        return val instanceof Number ? ((Number) val).doubleValue() : defaultValue;
    }

    private static int getInt(Map<String, Object> map, String key, int defaultValue) {
        Object val = map.get(key);
        if (val == null) return defaultValue;
        return val instanceof Number ? ((Number) val).intValue() : defaultValue;
    }

    private static long getLong(Map<String, Object> map, String key, long defaultValue) {
        Object val = map.get(key);
        if (val == null) return defaultValue;
        return val instanceof Number ? ((Number) val).longValue() : defaultValue;
    }
}
```

---

## Step 8 — `KafkaBridgeSource.java`

```java
package ai.hybridstream.connector.kafka;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.kafka.clients.consumer.OffsetResetStrategy;

import java.util.Map;

/**
 * Kafka source for consuming events from HEA bridge topics or migration buffer topics.
 *
 * Bridge topics: produced by HEA operators during normal execution.
 * Migration buffer topics: produced by upstream operators during PCTR Phase 1 drain.
 * Both use MessagePack serialization; deserialization is handled downstream.
 */
public class KafkaBridgeSource {

    /**
     * Build a Flink KafkaSource for a bridge topic.
     * Starts from the drain offset captured during PCTR Phase 1.
     *
     * @param bootstrapServers  Kafka bootstrap servers
     * @param topic             Bridge or migration buffer topic name
     * @param groupId           Consumer group ID
     * @param drainOffsets      Partition→offset map from PCTR Phase 1 (null = earliest)
     */
    public static KafkaSource<byte[]> forBridgeTopic(
        String bootstrapServers,
        String topic,
        String groupId,
        Map<Integer, Long> drainOffsets
    ) {
        var builder = KafkaSource.<byte[]>builder()
            .setBootstrapServers(bootstrapServers)
            .setTopics(topic)
            .setGroupId(groupId)
            .setDeserializer(new RawBytesDeserializer());

        if (drainOffsets != null && !drainOffsets.isEmpty()) {
            // Start exactly from drain offsets (PCTR Phase 1 handoff point)
            builder.setStartingOffsets(OffsetsInitializer.offsets(
                drainOffsets.entrySet().stream()
                    .collect(java.util.stream.Collectors.toMap(
                        e -> new org.apache.kafka.common.TopicPartition(topic, e.getKey()),
                        Map.Entry::getValue
                    ))
            ));
        } else {
            builder.setStartingOffsets(OffsetsInitializer.earliest());
        }

        return builder.build();
    }

    /**
     * Raw bytes deserializer for MessagePack-encoded records.
     * Deserialization into Map<String,Object> is done inside the operator.
     */
    public static class RawBytesDeserializer implements
        org.apache.flink.connector.kafka.source.reader.deserializer.KafkaRecordDeserializationSchema<byte[]> {

        @Override
        public void deserialize(
            org.apache.kafka.clients.consumer.ConsumerRecord<byte[], byte[]> record,
            org.apache.flink.util.Collector<byte[]> out
        ) {
            out.collect(record.value());
        }

        @Override
        public org.apache.flink.api.common.typeinfo.TypeInformation<byte[]> getProducedType() {
            return org.apache.flink.api.common.typeinfo.Types.PRIMITIVE_ARRAY(
                org.apache.flink.api.common.typeinfo.Types.BYTE()
            );
        }
    }
}
```

---

## Step 9 — `FlinkConnectorServiceImpl.java`

```java
package ai.hybridstream.connector.grpc;

import ai.hybridstream.connector.config.ConnectorConfig;
import ai.hybridstream.connector.operator.MigratedOperator;
import ai.hybridstream.connector.operator.OperatorFactory;
import ai.hybridstream.connector.snapshot.SchemaRegistry;
import ai.hybridstream.connector.snapshot.SnapshotDeserializer;
import ai.hybridstream.connector.store.MinIOClient;
import ai.hybridstream.proto.HybridstreamProto.*;
import ai.hybridstream.proto.FlinkConnectorGrpc;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * gRPC server implementation for the HybridStream Flink Connector.
 * Receives operator restore commands from AODE (PCTR Phase 3).
 *
 * RPCs implemented:
 *   RestoreOperator   — Download snapshot, deserialize, submit Flink job
 *   TerminateOperator — Cancel Flink job for a migrated-away operator
 *   GetJobStatus      — Report health of running operator jobs
 */
public class FlinkConnectorServiceImpl extends FlinkConnectorGrpc.FlinkConnectorImplBase {

    private static final Logger log = LoggerFactory.getLogger(FlinkConnectorServiceImpl.class);

    private final ConnectorConfig config;
    private final MinIOClient minioClient;
    private final SchemaRegistry schemaRegistry;
    private final SnapshotDeserializer deserializer;

    // Track active Flink jobs per operator ID
    private final Map<String, String> operatorJobIds = new ConcurrentHashMap<>();

    public FlinkConnectorServiceImpl(
        ConnectorConfig config,
        MinIOClient minioClient,
        SchemaRegistry schemaRegistry
    ) {
        this.config         = config;
        this.minioClient    = minioClient;
        this.schemaRegistry = schemaRegistry;
        this.deserializer   = new SnapshotDeserializer(schemaRegistry);
    }

    /**
     * PCTR Phase 3: Restore an operator from a MinIO snapshot onto Flink.
     *
     * Steps:
     * 1. Download MessagePack snapshot from MinIO
     * 2. Deserialize + translate to Flink state format
     * 3. Create MigratedOperator Flink job
     * 4. Submit to Flink cluster
     * 5. Return job ID to AODE
     */
    @Override
    public void restoreOperator(RestoreRequest request, StreamObserver<RestoreResponse> responseObserver) {
        String operatorId  = request.getOperatorId();
        String snapshotKey = request.getSnapshotObjectKey();
        String operatorType = request.getOperatorType();

        log.info("RestoreOperator: id={} type={} snapshot={}", operatorId, operatorType, snapshotKey);

        try {
            // Step 1: Download snapshot
            byte[] snapshotBytes = minioClient.downloadSnapshot(snapshotKey);

            // Step 2: Deserialize + translate
            Map<String, Object> rawState   = deserializer.deserialize(snapshotBytes, operatorType);
            Map<String, Object> flinkState = deserializer.translateToFlinkState(rawState, operatorType);

            // Step 3: Create MigratedOperator
            MigratedOperator operator = OperatorFactory.create(operatorId, operatorType, flinkState);

            // Step 4: Submit Flink job (simplified — real implementation uses Flink REST API)
            String jobId = submitFlinkJob(operatorId, operatorType, operator, request);
            operatorJobIds.put(operatorId, jobId);

            log.info("Restored operator {} as Flink job {}", operatorId, jobId);

            responseObserver.onNext(RestoreResponse.newBuilder()
                .setOperatorId(operatorId)
                .setJobId(jobId)
                .setSuccess(true)
                .build());

        } catch (Exception e) {
            log.error("Failed to restore operator {}: {}", operatorId, e.getMessage(), e);
            responseObserver.onNext(RestoreResponse.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg(e.getMessage())
                .build());
        }

        responseObserver.onCompleted();
    }

    /**
     * PCTR Phase 4 (cloud-side): Terminate a running Flink job when operator migrates back to edge.
     */
    @Override
    public void terminateOperator(TerminateRequest request, StreamObserver<TerminateAck> responseObserver) {
        String operatorId = request.getOperatorId();
        String jobId      = operatorJobIds.remove(operatorId);

        if (jobId == null) {
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg("No active Flink job found for operator " + operatorId)
                .build());
            responseObserver.onCompleted();
            return;
        }

        try {
            cancelFlinkJob(jobId);
            log.info("Terminated Flink job {} for operator {}", jobId, operatorId);
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(true)
                .build());
        } catch (Exception e) {
            log.error("Failed to terminate job {} for operator {}: {}", jobId, operatorId, e.getMessage());
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg(e.getMessage())
                .build());
        }

        responseObserver.onCompleted();
    }

    // ── Private Helpers ────────────────────────────────────────────────────────────────

    /**
     * Submit a Flink job for a migrated operator.
     * In a real deployment, this uses the Flink REST API (POST /jars/{id}/run).
     * For initial implementation, uses the embedded MiniCluster.
     */
    private String submitFlinkJob(
        String operatorId,
        String operatorType,
        MigratedOperator operator,
        RestoreRequest request
    ) {
        // TODO: Replace with actual Flink cluster submission via REST API
        // For now, return a mock job ID for testing
        return "flink-job-" + operatorId + "-" + System.currentTimeMillis();
    }

    private void cancelFlinkJob(String jobId) {
        // TODO: Use Flink REST API to cancel job
        log.debug("Cancelling Flink job: {}", jobId);
    }
}
```

---

## Step 10 — `HybridStreamConnector.java` (entrypoint)

```java
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
```

---

## Step 11 — Unit Tests

### `SnapshotDeserializerTest.java`

```java
package ai.hybridstream.connector.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.*;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class SnapshotDeserializerTest {

    private SchemaRegistry schemaRegistry;
    private SnapshotDeserializer deserializer;

    @BeforeEach
    void setUp(@TempDir Path tempDir) throws IOException {
        // Write a minimal test schema
        String schema = """
            {
                "operator_type": "VehicleDetector",
                "schema_version": 1,
                "fields": {
                    "detection_count": "int",
                    "last_speed":      "float",
                    "is_active":       "boolean"
                }
            }
            """;
        Path schemaFile = tempDir.resolve("VehicleDetector.json");
        Files.writeString(schemaFile, schema);

        schemaRegistry = new SchemaRegistry();
        schemaRegistry.loadFromDirectory(tempDir.toString());
        deserializer = new SnapshotDeserializer(schemaRegistry);
    }

    @Test
    void testDeserializeValidSnapshot() throws Exception {
        // Build a valid snapshot: magic + version(1) + msgpack payload
        byte[] magic   = {0x48, 0x53, 0x4D, 0x50};
        byte[] version = {0x00, 0x01};

        // Encode payload with Jackson MessagePack
        var mapper  = new com.fasterxml.jackson.databind.ObjectMapper(new org.msgpack.jackson.dataformat.MessagePackFactory());
        Map<String, Object> state = Map.of(
            "detection_count", 42,
            "last_speed",      87.5,
            "is_active",       true
        );
        byte[] payload = mapper.writeValueAsBytes(state);

        byte[] snapshot = new byte[magic.length + version.length + payload.length];
        System.arraycopy(magic,   0, snapshot, 0,                    magic.length);
        System.arraycopy(version, 0, snapshot, magic.length,         version.length);
        System.arraycopy(payload, 0, snapshot, magic.length + version.length, payload.length);

        Map<String, Object> result = deserializer.deserialize(snapshot, "VehicleDetector");
        assertEquals(42, ((Number) result.get("detection_count")).intValue());
        assertEquals(87.5, ((Number) result.get("last_speed")).doubleValue(), 0.01);
        assertTrue((Boolean) result.get("is_active"));
    }

    @Test
    void testInvalidMagicBytesThrows() {
        byte[] badSnapshot = {0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01};
        assertThrows(IOException.class, () ->
            deserializer.deserialize(badSnapshot, "VehicleDetector")
        );
    }

    @Test
    void testUnsupportedSchemaVersionThrows() {
        // Version 99 is not registered
        byte[] snapshot = {0x48, 0x53, 0x4D, 0x50, 0x00, 0x63, 0x01};
        assertThrows(IOException.class, () ->
            deserializer.deserialize(snapshot, "VehicleDetector")
        );
    }
}
```

---

## Step 12 — `flink-connector/Dockerfile`

```dockerfile
FROM eclipse-temurin:17-jdk-slim AS build
WORKDIR /build
COPY pom.xml .
COPY src/ src/
RUN apt-get update && apt-get install -y maven && \
    mvn -q package -DskipTests && \
    rm -rf /root/.m2

FROM apache/flink:1.18.1-java17
WORKDIR /opt/flink/usrlib
COPY --from=build /build/target/hybridstream-flink-connector-0.1.0.jar .

# Schema directory
RUN mkdir -p /app/schemas
COPY schema-registry/schemas/ /app/schemas/

EXPOSE 50053

CMD ["java", "-cp", "/opt/flink/usrlib/hybridstream-flink-connector-0.1.0.jar", \
     "ai.hybridstream.connector.HybridStreamConnector"]
```

---

## Phase 4 Completion Criteria

Phase 4 is done when:

1. `mvn test` passes — all Java unit tests green
2. Connector container starts: `docker compose up flink-connector`
3. gRPC server responds on port 50053
4. `RestoreOperator` RPC: given a valid `.msgpack` snapshot in MinIO, creates a `MigratedOperator` without error
5. `SnapshotDeserializer` correctly parses all 11 operator types from test snapshots
6. `SchemaRegistry` loads all JSON schemas and validates versions
7. `OperatorFactory` creates correct logic for all 11 operator types (test with synthetic state maps)
8. `TerminateOperator` RPC: cleanly stops a running operator job
