package ai.hybridstream.connector.snapshot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.msgpack.jackson.dataformat.MessagePackFactory;

import java.io.*;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class SnapshotDeserializerTest {

    private SchemaRegistry schemaRegistry;
    private SnapshotDeserializer deserializer;

    // ── Schema used in setUp includes every field type exercised by new tests ──
    @BeforeEach
    void setUp(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "VehicleDetector",
                "schema_version": 1,
                "fields": {
                    "detection_count": "int",
                    "last_speed":      "float",
                    "is_active":       "boolean",
                    "status_flag":     "bool",
                    "label":           "str",
                    "tags":            "list",
                    "meta":            "dict"
                }
            }
            """;
        Files.writeString(tempDir.resolve("VehicleDetector.json"), schema);

        schemaRegistry = new SchemaRegistry();
        schemaRegistry.loadFromDirectory(tempDir.toString());
        deserializer = new SnapshotDeserializer(schemaRegistry);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /** Build a valid HSMP snapshot from a state map using MessagePack. */
    private byte[] buildSnapshot(int schemaVersion, Map<String, Object> state) throws Exception {
        var mapper = new ObjectMapper(new MessagePackFactory());
        byte[] payload = mapper.writeValueAsBytes(state);
        byte[] snapshot = new byte[6 + payload.length];
        snapshot[0] = 0x48; snapshot[1] = 0x53; snapshot[2] = 0x4D; snapshot[3] = 0x50;
        snapshot[4] = (byte) ((schemaVersion >> 8) & 0xFF);
        snapshot[5] = (byte) (schemaVersion & 0xFF);
        System.arraycopy(payload, 0, snapshot, 6, payload.length);
        return snapshot;
    }

    // ── Original tests (kept verbatim) ────────────────────────────────────────

    @Test
    void testDeserializeValidSnapshot() throws Exception {
        byte[] magic   = {0x48, 0x53, 0x4D, 0x50};
        byte[] version = {0x00, 0x01};

        var mapper = new ObjectMapper(new MessagePackFactory());
        Map<String, Object> state = Map.of(
            "detection_count", 42,
            "last_speed",      87.5,
            "is_active",       true
        );
        byte[] payload = mapper.writeValueAsBytes(state);

        byte[] snapshot = new byte[magic.length + version.length + payload.length];
        System.arraycopy(magic,   0, snapshot, 0,                             magic.length);
        System.arraycopy(version, 0, snapshot, magic.length,                  version.length);
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

    @Test
    void testSnapshotTooSmallThrows() {
        byte[] tinySnapshot = {0x48, 0x53};  // Only 2 bytes, need at least 6
        assertThrows(IOException.class, () ->
            deserializer.deserialize(tinySnapshot, "VehicleDetector")
        );
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    /**
     * Python None serialises as MessagePack nil, which Jackson deserialises as Java
     * null.  translateToFlinkState must not throw NullPointerException when a field
     * value is null.
     */
    @Test
    void testNullFieldValueDoesNotCauseNpe() throws Exception {
        // MessagePack nil → Java null; use a raw map so we can put null values.
        Map<String, Object> rawState = new HashMap<>();
        rawState.put("detection_count", null);  // Python None
        rawState.put("last_speed", 55.0);

        byte[] snapshot = buildSnapshot(1, rawState);
        Map<String, Object> deserialized = deserializer.deserialize(snapshot, "VehicleDetector");

        // translateToFlinkState must not throw; the null field should remain null.
        assertDoesNotThrow(() -> {
            Map<String, Object> result = deserializer.translateToFlinkState(deserialized, "VehicleDetector");
            assertNull(result.get("detection_count"), "null Python value should translate to null Java value");
            assertEquals(55.0, ((Number) result.get("last_speed")).doubleValue(), 0.001);
        });
    }

    /**
     * "bool" is the canonical schema type name used by hybridstream-common for
     * Python booleans; it must translate to a Java Boolean without falling through
     * to the default (pass-through) branch.
     */
    @Test
    void testBoolTypeTranslatesCorrectly() throws Exception {
        Map<String, Object> rawState = Map.of("status_flag", true);
        byte[] snapshot = buildSnapshot(1, rawState);
        Map<String, Object> deserialized = deserializer.deserialize(snapshot, "VehicleDetector");

        Map<String, Object> result = deserializer.translateToFlinkState(deserialized, "VehicleDetector");

        assertInstanceOf(Boolean.class, result.get("status_flag"));
        assertTrue((Boolean) result.get("status_flag"));
    }

    /**
     * "str" schema type: Python str → Java String via value.toString().
     */
    @Test
    void testStrTypeTranslatesCorrectly() throws Exception {
        Map<String, Object> rawState = Map.of("label", "highway");
        byte[] snapshot = buildSnapshot(1, rawState);
        Map<String, Object> deserialized = deserializer.deserialize(snapshot, "VehicleDetector");

        Map<String, Object> result = deserializer.translateToFlinkState(deserialized, "VehicleDetector");

        assertEquals("highway", result.get("label"));
        assertInstanceOf(String.class, result.get("label"));
    }

    /**
     * "list" and "dict" schema types must pass through as-is (no conversion).
     * MessagePack/Jackson already deserialises them as java.util.List and java.util.Map.
     */
    @Test
    void testListAndDictTypesPassThrough() throws Exception {
        List<Object> tagList = List.of("cam1", "cam2");
        Map<String, Object> metaMap = Map.of("zone", "A", "priority", 1);

        Map<String, Object> rawState = new HashMap<>();
        rawState.put("tags", tagList);
        rawState.put("meta", metaMap);

        byte[] snapshot = buildSnapshot(1, rawState);
        Map<String, Object> deserialized = deserializer.deserialize(snapshot, "VehicleDetector");

        Map<String, Object> result = deserializer.translateToFlinkState(deserialized, "VehicleDetector");

        assertInstanceOf(List.class, result.get("tags"));
        assertInstanceOf(Map.class, result.get("meta"));
    }

    /**
     * Version 0 is structurally invalid (schema_version must be >= 1).
     * The deserializer must throw IOException with a meaningful message.
     */
    @Test
    void testVersionZeroThrowsUnsupportedVersion() {
        // Version byte [4..5] = 0x00 0x00 → version 0
        byte[] snapshot = {0x48, 0x53, 0x4D, 0x50, 0x00, 0x00, 0x01};
        assertThrows(IOException.class, () ->
            deserializer.deserialize(snapshot, "VehicleDetector"),
            "Version 0 should be rejected as unsupported"
        );
    }

    /**
     * A snapshot whose 6-byte header is valid but whose payload is an empty
     * MessagePack map (fixmap with 0 elements = 0x80) must deserialize without
     * exception and produce an empty state map.
     */
    @Test
    void testEmptyMessagePackMapProducesEmptyState() throws Exception {
        // 0x80 = MessagePack fixmap with 0 entries
        byte[] payload  = {(byte) 0x80};
        byte[] snapshot = new byte[6 + payload.length];
        snapshot[0] = 0x48; snapshot[1] = 0x53; snapshot[2] = 0x4D; snapshot[3] = 0x50;
        snapshot[4] = 0x00; snapshot[5] = 0x01; // version 1
        System.arraycopy(payload, 0, snapshot, 6, payload.length);

        Map<String, Object> result = deserializer.deserialize(snapshot, "VehicleDetector");
        assertNotNull(result);
        assertTrue(result.isEmpty(), "Empty MessagePack map should produce an empty Java map");
    }
}