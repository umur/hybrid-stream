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