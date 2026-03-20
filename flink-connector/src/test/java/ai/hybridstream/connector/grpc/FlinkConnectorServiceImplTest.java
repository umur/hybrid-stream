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

    @Test
    void testRestoreOperatorSuccess() throws Exception {
        String operatorId  = "test-operator";
        String snapshotKey = "test-snapshot-key";
        String operatorType = "VehicleDetector";

        when(minioClient.downloadSnapshot(snapshotKey)).thenReturn(buildValidSnapshot());

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperatorId(operatorId)
            .setSnapshotObjectKey(snapshotKey)
            .setOperatorType(operatorType)
            .build();

        service.restoreOperator(request, restoreResponseObserver);

        verify(minioClient).downloadSnapshot(snapshotKey);
        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            response.getSuccess() &&
            !response.getJobId().isEmpty()
        ));
        verify(restoreResponseObserver).onCompleted();
    }

    @Test
    void testRestoreOperatorFailure() throws Exception {
        String operatorId  = "test-operator";
        String snapshotKey = "test-snapshot-key";

        when(minioClient.downloadSnapshot(snapshotKey)).thenThrow(new RuntimeException("MinIO error"));

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperatorId(operatorId)
            .setSnapshotObjectKey(snapshotKey)
            .setOperatorType("VehicleDetector")
            .build();

        service.restoreOperator(request, restoreResponseObserver);

        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            !response.getSuccess() &&
            response.getErrorMsg().contains("MinIO error")
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
            .setOperatorId(operatorId)
            .setSnapshotObjectKey("test-key")
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
        // Arrange
        String operatorId = "nonexistent-operator";

        TerminateRequest request = TerminateRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        // Act
        service.terminateOperator(request, terminateResponseObserver);

        // Assert
        verify(terminateResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            !response.getSuccess() &&
            response.getErrorMsg().contains("No active Flink job found")
        ));
        verify(terminateResponseObserver).onCompleted();
    }

    @Test
    void testGetJobStatusNotFound() {
        // Arrange
        String operatorId = "nonexistent-operator";

        JobStatusRequest request = JobStatusRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        // Act
        service.getJobStatus(request, statusResponseObserver);

        // Assert
        verify(statusResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            response.getJobId().isEmpty() &&
            response.getStatus().equals("NOT_FOUND")
        ));
        verify(statusResponseObserver).onCompleted();
    }
}