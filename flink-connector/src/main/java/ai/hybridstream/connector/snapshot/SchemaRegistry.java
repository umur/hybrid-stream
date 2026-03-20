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
        if (operatorType == null || operatorType.isBlank()) {
            throw new IOException("Schema file missing 'operator_type' field: " + file.getName());
        }

        // Jackson deserialises JSON numbers as Integer or Long depending on magnitude.
        // Cast through Number to avoid ClassCastException on either type.
        Object versionObj = raw.get("schema_version");
        if (!(versionObj instanceof Number)) {
            throw new IOException("Schema file missing or non-numeric 'schema_version' field: " + file.getName());
        }
        int version = ((Number) versionObj).intValue();
        if (version <= 0) {
            throw new IOException(String.format(
                "Invalid schema_version %d in %s — version must be a positive integer", version, file.getName()));
        }

        Map<String, String> fields = (Map<String, String>) raw.get("fields");
        if (fields == null) {
            throw new IOException("Schema file missing 'fields' field: " + file.getName());
        }

        schemas.put(operatorType, fields);
        supportedVersions.computeIfAbsent(operatorType, k -> new HashSet<>()).add(version);

        log.debug("Loaded schema: type={} version={} fields={}", operatorType, version, fields.size());
    }

    public boolean isVersionSupported(String operatorType, int version) {
        // Version 0 and negative versions are structurally invalid — reject immediately.
        if (version <= 0) {
            return false;
        }
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