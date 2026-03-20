package ai.hybridstream.connector.operator;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

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
                // Defensive copy: the list from state may be an immutable List.of(...)
                // (e.g. produced by a prior ProcessResult) — mutating it directly would
                // throw UnsupportedOperationException.
                List<Double> window = new ArrayList<>((List<Double>) state.getOrDefault("window", new ArrayList<>()));
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

            case "MultiStreamJoin" -> (record, state) -> {
                // Join events from multiple streams by key
                String key = (String) record.getOrDefault("join_key", "unknown");
                @SuppressWarnings("unchecked")
                Map<String, Object> joinBuffer = (Map<String, Object>) state.getOrDefault("join_buffer", new HashMap<>());
                
                joinBuffer.put(key, record);
                Map<String, Object> newState = new HashMap<>(state);
                newState.put("join_buffer", joinBuffer);

                // For simplicity, emit immediately with join buffer
                Map<String, Object> output = new HashMap<>(record);
                output.put("joined_records", joinBuffer.size());
                
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
                // Defensive copy: map from state may be unmodifiable (e.g. Map.of or
                // a prior snapshot restored via Collections.unmodifiableMap).
                Map<String, Integer> counts = new HashMap<>((Map<String, Integer>) state.getOrDefault("zone_counts", new HashMap<>()));
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

            case "PatternDetector" -> (record, state) -> {
                // Pattern detection over sliding window
                @SuppressWarnings("unchecked")
                // Defensive copy: same immutability risk as FeatureAggWindow.
                List<Boolean> pattern = new ArrayList<>((List<Boolean>) state.getOrDefault("pattern", new ArrayList<>()));
                boolean detected = (boolean) record.getOrDefault("vehicle_detected", false);
                pattern.add(detected);

                // Keep last 10 events
                while (pattern.size() > 10) pattern.remove(0);

                // Detect "three in a row" pattern
                boolean patternDetected = false;
                if (pattern.size() >= 3) {
                    for (int i = 0; i <= pattern.size() - 3; i++) {
                        if (pattern.get(i) && pattern.get(i+1) && pattern.get(i+2)) {
                            patternDetected = true;
                            break;
                        }
                    }
                }

                Map<String, Object> newState = new HashMap<>(state);
                newState.put("pattern", pattern);

                Map<String, Object> output = new HashMap<>(record);
                output.put("pattern_detected", patternDetected);
                
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