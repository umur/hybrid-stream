package ai.hybridstream.connector.grpc;

import ai.hybridstream.connector.config.ConnectorConfig;
import ai.hybridstream.connector.snapshot.SchemaRegistry;
import ai.hybridstream.connector.store.MinIOClient;
import ai.hybridstream.proto.RestoreRequest;
import ai.hybridstream.proto.RestoreResponse;
import ai.hybridstream.proto.TerminateRequest;
import ai.hybridstream.proto.TerminateAck;
import ai.hybridstream.proto.JobStatusRequest;
import ai.hybridstream.proto.JobStatusResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.grpc.stub.StreamObserver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.msgpack.jackson.dataformat.MessagePackFactory;

import java.nio.file.*;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class FlinkConnectorServiceImplTest {

    @TempDir
    Path schemaDir;

    @Mock
    private MinIOClient minioClient;

    @Mock
    private StreamObserver<RestoreResponse> restoreResponseObserver;

    @Mock
    private StreamObserver<TerminateAck> terminateResponseObserver;

    @Mock
    private StreamObserver<JobStatusResponse> statusResponseObserver;

    private FlinkConnectorServiceImpl service;
    private ConnectorConfig config;
    private SchemaRegistry schemaRegistry;

    /** Builds a valid HSMP-encoded MessagePack snapshot for VehicleDetector. */
    private byte[] buildValidSnapshot() throws Exception {
        var mapper = new ObjectMapper(new MessagePackFactory());
        byte[] payload = mapper.writeValueAsBytes(Map.of(
            "detection_count", 5,
            "last_speed", 88.0,
            "is_active", true
        ));
        byte[] snapshot = new byte[6 + payload.length];
        snapshot[0] = 0x48; snapshot[1] = 0x53; snapshot[2] = 0x4D; snapshot[3] = 0x50; // HSMP
        snapshot[4] = 0x00; snapshot[5] = 0x01; // version 1
        System.arraycopy(payload, 0, snapshot, 6, payload.length);
        return snapshot;
    }

    @BeforeEach
    void setUp() throws Exception {
        // Write VehicleDetector schema to temp dir
        String schema = """
            {"operator_type":"VehicleDetector","schema_version":1,
             "fields":{"detection_count":"int","last_speed":"float","is_active":"boolean"}}
            """;
        Files.writeString(schemaDir.resolve("VehicleDetector.json"), schema);

        config = ConnectorConfig.fromEnv();
        config.schemaDir = schemaDir.toString();

        schemaRegistry = new SchemaRegistry();
        schemaRegistry.loadFromDirectory(schemaDir.toString());

        service = new FlinkConnectorServiceImpl(config, minioClient, schemaRegistry);
    }

    // ── Proto field reference guide (from hybridstream.proto) ─────────────────
    // RestoreRequest  : operation_id, operator_id, object_key, operator_type, drain_offset
    // RestoreResponse : operation_id, success, flink_job_id, error_message, started_at_ms
    // TerminateRequest: operator_id, flush_state, migration_buffer_topic
    // TerminateAck    : operator_id, success, error_msg
    // JobStatusRequest: flink_job_id
    // JobStatusResponse: operator_id, job_id, status, last_checkpoint, metrics_json

    @Test
    void testRestoreOperatorSuccess() throws Exception {
        String operatorId   = "test-operator";
        String snapshotKey  = "test-snapshot-key";
        String operatorType = "VehicleDetector";
        String operationId  = "op-001";

        when(minioClient.downloadSnapshot(snapshotKey)).thenReturn(buildValidSnapshot());

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperationId(operationId)
            .setOperatorId(operatorId)
            .setObjectKey(snapshotKey)
            .setOperatorType(operatorType)
            .build();

        service.restoreOperator(request, restoreResponseObserver);

        verify(minioClient).downloadSnapshot(snapshotKey);
        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperationId().equals(operationId) &&
            response.getSuccess() &&
            !response.getFlinkJobId().isEmpty()
        ));
        verify(restoreResponseObserver).onCompleted();
    }

    @Test
    void testRestoreOperatorFailure() throws Exception {
        String operatorId  = "test-operator";
        String snapshotKey = "test-snapshot-key";
        String operationId = "op-002";

        when(minioClient.downloadSnapshot(snapshotKey)).thenThrow(new RuntimeException("MinIO error"));

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperationId(operationId)
            .setOperatorId(operatorId)
            .setObjectKey(snapshotKey)
            .setOperatorType("VehicleDetector")
            .build();

        service.restoreOperator(request, restoreResponseObserver);

        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperationId().equals(operationId) &&
            !response.getSuccess() &&
            response.getErrorMessage().contains("MinIO error")
        ));
        verify(restoreResponseObserver).onCompleted();
    }

    @Test
    @SuppressWarnings("unchecked")
    void testTerminateOperatorFound() throws Exception {
        String operatorId = "test-operator";

        // Restore first to register a job ID
        when(minioClient.downloadSnapshot(anyString())).thenReturn(buildValidSnapshot());
        RestoreRequest restoreRequest = RestoreRequest.newBuilder()
            .setOperationId("op-003")
            .setOperatorId(operatorId)
            .setObjectKey("test-key")
            .setOperatorType("VehicleDetector")
            .build();
        service.restoreOperator(restoreRequest, mock(StreamObserver.class));

        // Now terminate
        TerminateRequest request = TerminateRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        service.terminateOperator(request, terminateResponseObserver);

        verify(terminateResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            response.getSuccess()
        ));
        verify(terminateResponseObserver).onCompleted();
    }

    @Test
    void testTerminateOperatorNotFound() {
        String operatorId = "nonexistent-operator";

        TerminateRequest request = TerminateRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        service.terminateOperator(request, terminateResponseObserver);

        verify(terminateResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            !response.getSuccess() &&
            response.getErrorMsg().contains("No active Flink job found")
        ));
        verify(terminateResponseObserver).onCompleted();
    }

    @Test
    void testGetJobStatusNotFound() {
        // Use a flink_job_id that was never registered
        String unknownJobId = "flink-job-nonexistent";

        JobStatusRequest request = JobStatusRequest.newBuilder()
            .setFlinkJobId(unknownJobId)
            .build();

        service.getJobStatus(request, statusResponseObserver);

        verify(statusResponseObserver).onNext(argThat(response ->
            response.getJobId().isEmpty() &&
            response.getStatus().equals("NOT_FOUND")
        ));
        verify(statusResponseObserver).onCompleted();
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    /**
     * When the exception thrown during snapshot download has a null message
     * (as NullPointerException does by default), restoreOperator must not itself
     * throw a NullPointerException when constructing the error response proto.
     * The error_message field must fall back to the exception class name.
     */
    @Test
    void testRestoreOperatorWithNullExceptionMessage() throws Exception {
        String operatorId  = "null-msg-operator";
        String snapshotKey = "any-key";
        String operationId = "op-npe";

        // NullPointerException with no message → getMessage() returns null
        when(minioClient.downloadSnapshot(snapshotKey))
            .thenThrow(new NullPointerException());   // getMessage() == null

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperationId(operationId)
            .setOperatorId(operatorId)
            .setObjectKey(snapshotKey)
            .setOperatorType("VehicleDetector")
            .build();

        // Must not throw
        assertDoesNotThrow(() -> service.restoreOperator(request, restoreResponseObserver));

        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperationId().equals(operationId) &&
            !response.getSuccess() &&
            // Fallback must be the class name (not null, not empty)
            !response.getErrorMessage().isEmpty()
        ));
        verify(restoreResponseObserver).onCompleted();
    }

    /**
     * terminateOperator for an operator that was never restored must respond with
     * success=false and an error_msg that identifies the operator.
     * Verifies that onCompleted is called exactly once (no double-completion).
     */
    @Test
    void testTerminateNonExistentOperatorReturnsDescriptiveError() {
        String operatorId = "ghost-operator-" + System.nanoTime();

        TerminateRequest request = TerminateRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        service.terminateOperator(request, terminateResponseObserver);

        verify(terminateResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            !response.getSuccess() &&
            response.getErrorMsg().contains(operatorId)
        ));
        // onCompleted must be called exactly once even in the not-found branch
        verify(terminateResponseObserver, times(1)).onCompleted();
    }
}
