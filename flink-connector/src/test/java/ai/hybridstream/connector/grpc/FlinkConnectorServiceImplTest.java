package ai.hybridstream.connector.grpc;

import ai.hybridstream.connector.config.ConnectorConfig;
import ai.hybridstream.connector.snapshot.SchemaRegistry;
import ai.hybridstream.connector.snapshot.SnapshotDeserializer;
import ai.hybridstream.connector.store.MinIOClient;
import ai.hybridstream.proto.RestoreRequest;
import ai.hybridstream.proto.RestoreResponse;
import ai.hybridstream.proto.TerminateRequest;
import ai.hybridstream.proto.TerminateAck;
import ai.hybridstream.proto.JobStatusRequest;
import ai.hybridstream.proto.JobStatusResponse;
import io.grpc.stub.StreamObserver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class FlinkConnectorServiceImplTest {

    @Mock
    private ConnectorConfig config;

    @Mock
    private MinIOClient minioClient;

    @Mock
    private SchemaRegistry schemaRegistry;

    @Mock
    private SnapshotDeserializer deserializer;

    @Mock
    private StreamObserver<RestoreResponse> restoreResponseObserver;

    @Mock
    private StreamObserver<TerminateAck> terminateResponseObserver;

    @Mock
    private StreamObserver<JobStatusResponse> statusResponseObserver;

    private FlinkConnectorServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new FlinkConnectorServiceImpl(config, minioClient, schemaRegistry);
    }

    @Test
    void testRestoreOperatorSuccess() throws Exception {
        // Arrange
        String operatorId = "test-operator";
        String snapshotKey = "test-snapshot-key";
        String operatorType = "VehicleDetector";

        byte[] snapshotBytes = "mock-snapshot-data".getBytes();
        Map<String, Object> rawState = Map.of("field1", "value1");
        Map<String, Object> flinkState = Map.of("field1", "translated-value1");

        when(minioClient.downloadSnapshot(snapshotKey)).thenReturn(snapshotBytes);
        when(schemaRegistry.getSchema(operatorType)).thenReturn(Map.of("field1", "string"));

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperatorId(operatorId)
            .setSnapshotObjectKey(snapshotKey)
            .setOperatorType(operatorType)
            .build();

        // Act
        service.restoreOperator(request, restoreResponseObserver);

        // Assert
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
        // Arrange
        String operatorId = "test-operator";
        String snapshotKey = "test-snapshot-key";
        
        when(minioClient.downloadSnapshot(snapshotKey)).thenThrow(new RuntimeException("MinIO error"));

        RestoreRequest request = RestoreRequest.newBuilder()
            .setOperatorId(operatorId)
            .setSnapshotObjectKey(snapshotKey)
            .setOperatorType("VehicleDetector")
            .build();

        // Act
        service.restoreOperator(request, restoreResponseObserver);

        // Assert
        verify(restoreResponseObserver).onNext(argThat(response ->
            response.getOperatorId().equals(operatorId) &&
            !response.getSuccess() &&
            response.getErrorMsg().contains("MinIO error")
        ));
        verify(restoreResponseObserver).onCompleted();
    }

    @Test
    void testTerminateOperatorFound() {
        // Arrange - first restore an operator to create a job
        String operatorId = "test-operator";
        try {
            when(minioClient.downloadSnapshot(anyString())).thenReturn("mock-data".getBytes());
            when(schemaRegistry.getSchema(anyString())).thenReturn(Map.of());
            
            RestoreRequest restoreRequest = RestoreRequest.newBuilder()
                .setOperatorId(operatorId)
                .setSnapshotObjectKey("test-key")
                .setOperatorType("VehicleDetector")
                .build();
            service.restoreOperator(restoreRequest, mock(StreamObserver.class));
        } catch (Exception e) {
            // Ignore for test setup
        }

        TerminateRequest request = TerminateRequest.newBuilder()
            .setOperatorId(operatorId)
            .build();

        // Act
        service.terminateOperator(request, terminateResponseObserver);

        // Assert
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