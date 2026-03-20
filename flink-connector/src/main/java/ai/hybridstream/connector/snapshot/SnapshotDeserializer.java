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

        if (snapshotBytes.length < HEADER_SIZE) {
            throw new IOException("Snapshot too small: " + snapshotBytes.length + " bytes, expected at least " + HEADER_SIZE);
        }

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