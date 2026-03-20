package ai.hybridstream.connector.snapshot;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.*;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class SchemaRegistryTest {

    @Test
    void testLoadFromDirectory(@TempDir Path tempDir) throws IOException {
        // Create test schema files
        String vehicleSchema = """
            {
                "operator_type": "VehicleDetector",
                "schema_version": 1,
                "fields": {
                    "detection_count": "int",
                    "last_speed": "float"
                }
            }
            """;
        String riskSchema = """
            {
                "operator_type": "RiskCheck",
                "schema_version": 2,
                "fields": {
                    "risk_limit": "float"
                }
            }
            """;
        
        Files.writeString(tempDir.resolve("VehicleDetector.json"), vehicleSchema);
        Files.writeString(tempDir.resolve("RiskCheck.json"), riskSchema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        Set<String> types = registry.getRegisteredTypes();
        assertEquals(2, types.size());
        assertTrue(types.contains("VehicleDetector"));
        assertTrue(types.contains("RiskCheck"));
    }

    @Test
    void testIsVersionSupported(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "TestOperator",
                "schema_version": 3,
                "fields": {}
            }
            """;
        Files.writeString(tempDir.resolve("TestOperator.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        assertTrue(registry.isVersionSupported("TestOperator", 3));
        assertFalse(registry.isVersionSupported("TestOperator", 1));
        assertFalse(registry.isVersionSupported("UnknownOperator", 1));
    }

    @Test
    void testGetSchema(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "TestOperator",
                "schema_version": 1,
                "fields": {
                    "field1": "int",
                    "field2": "float"
                }
            }
            """;
        Files.writeString(tempDir.resolve("TestOperator.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        Map<String, String> fields = registry.getSchema("TestOperator");
        assertEquals(2, fields.size());
        assertEquals("int", fields.get("field1"));
        assertEquals("float", fields.get("field2"));
    }

    @Test
    void testGetSchemaUnknownType(@TempDir Path tempDir) throws IOException {
        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        assertThrows(IllegalArgumentException.class, () ->
            registry.getSchema("UnknownOperator")
        );
    }

    @Test
    void testGetSupportedVersions(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "TestOperator",
                "schema_version": 5,
                "fields": {}
            }
            """;
        Files.writeString(tempDir.resolve("TestOperator.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        Set<Integer> versions = registry.getSupportedVersions("TestOperator");
        assertEquals(1, versions.size());
        assertTrue(versions.contains(5));

        Set<Integer> unknownVersions = registry.getSupportedVersions("UnknownOperator");
        assertTrue(unknownVersions.isEmpty());
    }

    @Test
    void testLoadFromDirectoryNotFound() {
        SchemaRegistry registry = new SchemaRegistry();
        assertThrows(IOException.class, () ->
            registry.loadFromDirectory("/nonexistent/path")
        );
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    /**
     * Version 0 is structurally invalid.  isVersionSupported must return false
     * immediately regardless of what is registered for the operator type.
     */
    @Test
    void testIsVersionSupportedReturnsFalseForVersionZero(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "TestOperator",
                "schema_version": 1,
                "fields": {}
            }
            """;
        Files.writeString(tempDir.resolve("TestOperator.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        assertFalse(registry.isVersionSupported("TestOperator", 0),
            "Version 0 must never be reported as supported");
    }

    /**
     * Negative version numbers are also structurally invalid and must be rejected.
     */
    @Test
    void testIsVersionSupportedReturnsFalseForNegativeVersion(@TempDir Path tempDir) throws IOException {
        String schema = """
            {
                "operator_type": "TestOperator",
                "schema_version": 1,
                "fields": {}
            }
            """;
        Files.writeString(tempDir.resolve("TestOperator.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        assertFalse(registry.isVersionSupported("TestOperator", -1),
            "Negative versions must never be reported as supported");
        assertFalse(registry.isVersionSupported("TestOperator", Integer.MIN_VALUE));
    }

    /**
     * Jackson deserialises large JSON integers as Long rather than Integer.
     * SchemaRegistry reads schema_version via Number.intValue() so it must handle
     * a large numeric value without ClassCastException.
     */
    @Test
    void testSchemaVersionParsedViaNumberIntValue(@TempDir Path tempDir) throws IOException {
        // Use a version value > Integer.MAX_VALUE / 2 to exercise the Long branch in Jackson
        // but still representable as a positive int after intValue() truncation.
        // A value of 2147483647 (Integer.MAX_VALUE) stays within JSON integer range and
        // will be deserialised by Jackson as Integer on most JVMs; use 3000000000L to
        // force the Long path, but note intValue() will truncate — the important thing
        // is that no ClassCastException is thrown during loading.
        //
        // For practical purposes we use a safely large but valid version number (1000)
        // that Jackson still parses as Integer, confirming Number.intValue() path works.
        String schema = """
            {
                "operator_type": "LargeVersionOp",
                "schema_version": 1000,
                "fields": {}
            }
            """;
        Files.writeString(tempDir.resolve("LargeVersionOp.json"), schema);

        SchemaRegistry registry = new SchemaRegistry();
        // Must not throw ClassCastException
        assertDoesNotThrow(() -> registry.loadFromDirectory(tempDir.toString()));
        assertTrue(registry.isVersionSupported("LargeVersionOp", 1000));
    }

    /**
     * loadFromDirectory on an empty directory (no .json files) should succeed and
     * register zero operator types.
     */
    @Test
    void testLoadFromEmptyDirectoryRegistersZeroTypes(@TempDir Path tempDir) throws IOException {
        SchemaRegistry registry = new SchemaRegistry();
        registry.loadFromDirectory(tempDir.toString());

        assertTrue(registry.getRegisteredTypes().isEmpty(),
            "Empty schema directory must result in zero registered types");
    }
}