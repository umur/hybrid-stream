package ai.hybridstream.connector.operator;

import org.junit.jupiter.api.Test;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class OperatorFactoryTest {

    @Test
    void testNormalizerOperator() {
        Map<String, Object> state = Map.of("mean", 10.0, "std", 2.0);
        MigratedOperator operator = OperatorFactory.create("test", "NormalizerOperator", state);
        assertNotNull(operator);
        // Operator creation should succeed without throwing
    }

    @Test
    void testFeatureAggWindow() {
        Map<String, Object> state = Map.of("window_size", 50);
        MigratedOperator operator = OperatorFactory.create("test", "FeatureAggWindow", state);
        assertNotNull(operator);
    }

    @Test
    void testMultiStreamJoin() {
        Map<String, Object> state = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "MultiStreamJoin", state);
        assertNotNull(operator);
    }

    @Test
    void testBinaryClassifier() {
        Map<String, Object> state = Map.of("threshold", 0.7);
        MigratedOperator operator = OperatorFactory.create("test", "BinaryClassifier", state);
        assertNotNull(operator);
    }

    @Test
    void testVehicleDetector() {
        Map<String, Object> state = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "VehicleDetector", state);
        assertNotNull(operator);
    }

    @Test
    void testZoneAggregator() {
        Map<String, Object> state = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "ZoneAggregator", state);
        assertNotNull(operator);
    }

    @Test
    void testPatternDetector() {
        Map<String, Object> state = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "PatternDetector", state);
        assertNotNull(operator);
    }

    @Test
    void testRiskCheck() {
        Map<String, Object> state = Map.of("risk_limit", 500000.0);
        MigratedOperator operator = OperatorFactory.create("test", "RiskCheck", state);
        assertNotNull(operator);
    }

    @Test
    void testAnomalyDetector() {
        Map<String, Object> state = Map.of("ewma_mean", 15.0, "ewma_std", 3.0);
        MigratedOperator operator = OperatorFactory.create("test", "AnomalyDetector", state);
        assertNotNull(operator);
    }

    @Test
    void testStatAggregator() {
        Map<String, Object> state = Map.of("count", 0L, "sum", 0.0, "m2", 0.0);
        MigratedOperator operator = OperatorFactory.create("test", "StatAggregator", state);
        assertNotNull(operator);
    }

    @Test
    void testComplianceLogger() {
        Map<String, Object> state = Map.of("logged_count", 0L);
        MigratedOperator operator = OperatorFactory.create("test", "ComplianceLogger", state);
        assertNotNull(operator);
    }

    @Test
    void testUnknownOperatorUsesPassthrough() {
        Map<String, Object> state = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "UnknownOperator", state);
        assertNotNull(operator);
        // Should create operator with pass-through logic without throwing
    }

    @Test
    void testCreateWithNullState() {
        MigratedOperator operator = OperatorFactory.create("test", "VehicleDetector", null);
        assertNotNull(operator);
    }

    @Test
    void testCreateWithEmptyState() {
        Map<String, Object> emptyState = new HashMap<>();
        MigratedOperator operator = OperatorFactory.create("test", "RiskCheck", emptyState);
        assertNotNull(operator);
    }
}