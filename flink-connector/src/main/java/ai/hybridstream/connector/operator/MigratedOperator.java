package ai.hybridstream.connector.operator;

import org.apache.flink.api.common.functions.RichFlatMapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.TypeHint;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.util.Collector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
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
    // restoredState is only used in open() before the operator is distributed.
    // Marked transient so Flink's serialization framework does not attempt to
    // serialise the raw Map (which may contain non-serializable values from
    // MessagePack deserialization). State is seeded into flinkState inside open().
    private transient Map<String, Object> restoredState;
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

        // Types.MAP(Types.STRING, Types.POJO(Object.class)) is invalid: Object is not a
        // POJO type and causes an InvalidTypesException at runtime.
        // Use TypeInformation.of(new TypeHint<>(){}) which resolves the full generic type
        // via reflection and falls back to Kryo serialization for the map values.
        ValueStateDescriptor<Map<String, Object>> descriptor =
            new ValueStateDescriptor<>(
                "operator-state-" + operatorId,
                TypeInformation.of(new TypeHint<Map<String, Object>>() {})
            );
        flinkState = getRuntimeContext().getState(descriptor);

        // Restore state from PCTR snapshot into Flink state.
        // Use a defensive copy so operator mutations during flatMap do not alias
        // back into the original restoredState map (which may still be referenced
        // by the constructor argument after open() returns in local-mode tests).
        if (restoredState != null && !restoredState.isEmpty()) {
            flinkState.update(new HashMap<>(restoredState));
            log.info("Restored {} state for operator {}: {} fields", operatorType, operatorId, restoredState.size());
            // Release the reference so the snapshot bytes can be GC'd after open().
            restoredState = null;
        }
    }

    @Override
    public void flatMap(Map<String, Object> record, Collector<Map<String, Object>> out) throws Exception {
        Map<String, Object> currentState = flinkState.value();
        if (currentState == null) {
            currentState = new java.util.HashMap<>();
        }

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
     * Interface for type-specific operator processing logic.
     * Implemented per operator type in OperatorFactory.
     */
    public interface OperatorLogic {

        ProcessResult process(Map<String, Object> record, Map<String, Object> currentState);

        /**
         * Result of processing a single record.
         */
        record ProcessResult(
            Map<String, Object> newState,
            java.util.List<Map<String, Object>> outputRecords
        ) {}
    }
}