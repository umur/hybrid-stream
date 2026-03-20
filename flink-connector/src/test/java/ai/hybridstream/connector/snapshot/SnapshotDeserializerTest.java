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

    @Test
    void testSnapshotTooSmallThrows() {
        byte[] tinySnapshot = {0x48, 0x53};  // Only 2 bytes, need at least 6
        assertThrows(IOException.class, () ->
            deserializer.deserialize(tinySnapshot, "VehicleDetector")
        );
    }
}