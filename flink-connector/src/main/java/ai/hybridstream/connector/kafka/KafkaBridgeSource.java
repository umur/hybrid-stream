package ai.hybridstream.connector.kafka;

import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.kafka.common.TopicPartition;

import java.util.Map;

/**
 * Kafka source for consuming events from HEA bridge topics or migration buffer topics.
 *
 * Bridge topics: produced by HEA operators during normal execution.
 * Migration buffer topics: produced by upstream operators during PCTR Phase 1 drain.
 * Both use MessagePack serialization; deserialization is handled downstream.
 */
public class KafkaBridgeSource {

    /**
     * Build a Flink KafkaSource for a bridge topic.
     * Starts from the drain offset captured during PCTR Phase 1.
     *
     * @param bootstrapServers  Kafka bootstrap servers
     * @param topic             Bridge or migration buffer topic name
     * @param groupId           Consumer group ID
     * @param drainOffsets      Partition→offset map from PCTR Phase 1 (null = earliest)
     */
    public static KafkaSource<byte[]> forBridgeTopic(
        String bootstrapServers,
        String topic,
        String groupId,
        Map<Integer, Long> drainOffsets
    ) {
        var builder = KafkaSource.<byte[]>builder()
            .setBootstrapServers(bootstrapServers)
            .setTopics(topic)
            .setGroupId(groupId)
            .setDeserializer(new RawBytesDeserializer());

        if (drainOffsets != null && !drainOffsets.isEmpty()) {
            // Start exactly from drain offsets (PCTR Phase 1 handoff point)
            builder.setStartingOffsets(OffsetsInitializer.offsets(
                drainOffsets.entrySet().stream()
                    .collect(java.util.stream.Collectors.toMap(
                        e -> new TopicPartition(topic, e.getKey()),
                        Map.Entry::getValue
                    ))
            ));
        } else {
            builder.setStartingOffsets(OffsetsInitializer.earliest());
        }

        return builder.build();
    }

    /**
     * Raw bytes deserializer for MessagePack-encoded records.
     * Deserialization into Map<String,Object> is done inside the operator.
     */
    public static class RawBytesDeserializer implements
        org.apache.flink.connector.kafka.source.reader.deserializer.KafkaRecordDeserializationSchema<byte[]> {

        @Override
        public void deserialize(
            org.apache.kafka.clients.consumer.ConsumerRecord<byte[], byte[]> record,
            org.apache.flink.util.Collector<byte[]> out
        ) {
            out.collect(record.value());
        }

        @Override
        public org.apache.flink.api.common.typeinfo.TypeInformation<byte[]> getProducedType() {
            return org.apache.flink.api.common.typeinfo.PrimitiveArrayTypeInfo.BYTE_PRIMITIVE_ARRAY_TYPE_INFO;
        }
    }
}