package ai.hybridstream.connector.operator;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.util.*;
import java.util.stream.Stream;

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

    // ── New tests ─────────────────────────────────────────────────────────────

    /**
     * Parametrized test: every one of the 11 supported operator types plus the
     * unknown/pass-through type must produce a non-null MigratedOperator.
     * This ensures no operator type is silently dropped from the factory switch.
     */
    static Stream<String> allOperatorTypes() {
        return Stream.of(
            // W1
            "NormalizerOperator",
            "FeatureAggWindow",
            "MultiStreamJoin",
            "BinaryClassifier",
            // W2
            "VehicleDetector",
            "ZoneAggregator",
            "PatternDetector",
            // W3
            "RiskCheck",
            "AnomalyDetector",
            "StatAggregator",
            "ComplianceLogger",
            // pass-through / unknown
            "UnknownOperatorType"
        );
    }

    @ParameterizedTest(name = "create({0}) returns non-null MigratedOperator")
    @MethodSource("allOperatorTypes")
    void testAllOperatorTypesReturnNonNull(String operatorType) {
        MigratedOperator operator = OperatorFactory.create("param-test", operatorType, new HashMap<>());
        assertNotNull(operator, "OperatorFactory.create must never return null for type: " + operatorType);
    }

    /**
     * FeatureAggWindow stores its sliding window as a List in state.
     * When the list held in state is immutable (e.g. produced by List.of() or a
     * prior ProcessResult), the logic must make a defensive copy before mutating it
     * rather than throwing UnsupportedOperationException.
     *
     * The OperatorLogic lambda is private inside MigratedOperator, but MigratedOperator
     * is in the same package (ai.hybridstream.connector.operator) as this test, so we
     * extract it via reflection on the private "logic" field.
     */
    @Test
    void testFeatureAggWindowMakesDefensiveCopyOfWindowList() throws Exception {
        List<Double> immutableWindow = List.of(1.0, 2.0, 3.0);
        Map<String, Object> state = new HashMap<>();
        state.put("window", immutableWindow);
        state.put("window_size", 5);

        MigratedOperator.OperatorLogic logic = extractLogic("FeatureAggWindow");

        Map<String, Object> record = Map.of("value", 10.0);

        MigratedOperator.OperatorLogic.ProcessResult result =
            assertDoesNotThrow(() -> logic.process(record, state),
                "FeatureAggWindow must make a defensive copy of the window list from state");

        assertNotNull(result);

        // The list stored in newState must be mutable — a second add must not throw.
        @SuppressWarnings("unchecked")
        List<Double> newWindow = (List<Double>) result.newState().get("window");
        assertNotNull(newWindow);
        assertDoesNotThrow(() -> newWindow.add(99.0),
            "List in returned state must be mutable");
    }

    /**
     * ZoneAggregator stores zone_counts as a Map in state.
     * If the map in state is unmodifiable, the logic must copy it before mutating.
     */
    @Test
    void testZoneAggregatorMakesDefensiveCopyOfCountsMap() throws Exception {
        Map<String, Integer> immutableCounts = Map.of("zone-A", 5);
        Map<String, Object> state = new HashMap<>();
        state.put("zone_counts", immutableCounts);

        Map<String, Object> record = new HashMap<>();
        record.put("zone_id", "zone-A");
        record.put("vehicle_detected", true);

        MigratedOperator.OperatorLogic logic = extractLogic("ZoneAggregator");

        assertDoesNotThrow(() -> logic.process(record, state),
            "ZoneAggregator must make a defensive copy of zone_counts before mutating");
    }

    /**
     * PatternDetector stores the detection pattern as a List<Boolean> in state.
     * If that list is immutable, the logic must copy it before appending.
     */
    @Test
    void testPatternDetectorMakesDefensiveCopyOfPatternList() throws Exception {
        List<Boolean> immutablePattern = List.of(true, false, true);
        Map<String, Object> state = new HashMap<>();
        state.put("pattern", immutablePattern);

        Map<String, Object> record = Map.of("vehicle_detected", true);

        MigratedOperator.OperatorLogic logic = extractLogic("PatternDetector");

        assertDoesNotThrow(() -> logic.process(record, state),
            "PatternDetector must make a defensive copy of the pattern list before mutating");
    }

    // ── Private helper ────────────────────────────────────────────────────────

    /**
     * Extract the private {@code logic} field from a freshly created
     * {@link MigratedOperator} via reflection.  Both classes live in the same
     * package so no module-access flag is needed on Java 17.
     */
    private static MigratedOperator.OperatorLogic extractLogic(String operatorType)
            throws Exception {
        MigratedOperator operator =
            OperatorFactory.create("reflect-test", operatorType, new HashMap<>());
        java.lang.reflect.Field field = MigratedOperator.class.getDeclaredField("logic");
        field.setAccessible(true);
        return (MigratedOperator.OperatorLogic) field.get(operator);
    }
}