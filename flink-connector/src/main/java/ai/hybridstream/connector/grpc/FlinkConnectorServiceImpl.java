package ai.hybridstream.connector.grpc;

import ai.hybridstream.connector.config.ConnectorConfig;
import ai.hybridstream.connector.operator.MigratedOperator;
import ai.hybridstream.connector.operator.OperatorFactory;
import ai.hybridstream.connector.snapshot.SchemaRegistry;
import ai.hybridstream.connector.snapshot.SnapshotDeserializer;
import ai.hybridstream.connector.store.MinIOClient;
import ai.hybridstream.proto.FlinkConnectorGrpc;
import ai.hybridstream.proto.RestoreRequest;
import ai.hybridstream.proto.RestoreResponse;
import ai.hybridstream.proto.TerminateRequest;
import ai.hybridstream.proto.TerminateAck;
import ai.hybridstream.proto.JobStatusRequest;
import ai.hybridstream.proto.JobStatusResponse;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * gRPC server implementation for the HybridStream Flink Connector.
 * Receives operator restore commands from AODE (PCTR Phase 3).
 *
 * RPCs implemented:
 *   RestoreOperator   — Download snapshot, deserialize, submit Flink job
 *   TerminateOperator — Cancel Flink job for a migrated-away operator
 *   GetJobStatus      — Report health of running operator jobs
 */
public class FlinkConnectorServiceImpl extends FlinkConnectorGrpc.FlinkConnectorImplBase {

    private static final Logger log = LoggerFactory.getLogger(FlinkConnectorServiceImpl.class);

    private final ConnectorConfig config;
    private final MinIOClient minioClient;
    private final SchemaRegistry schemaRegistry;
    private final SnapshotDeserializer deserializer;

    // Track active Flink jobs per operator ID
    private final Map<String, String> operatorJobIds = new ConcurrentHashMap<>();

    public FlinkConnectorServiceImpl(
        ConnectorConfig config,
        MinIOClient minioClient,
        SchemaRegistry schemaRegistry
    ) {
        this.config         = config;
        this.minioClient    = minioClient;
        this.schemaRegistry = schemaRegistry;
        this.deserializer   = new SnapshotDeserializer(schemaRegistry);
    }

    /**
     * PCTR Phase 3: Restore an operator from a MinIO snapshot onto Flink.
     *
     * Steps:
     * 1. Download MessagePack snapshot from MinIO
     * 2. Deserialize + translate to Flink state format
     * 3. Create MigratedOperator Flink job
     * 4. Submit to Flink cluster
     * 5. Return job ID to AODE
     */
    @Override
    public void restoreOperator(RestoreRequest request, StreamObserver<RestoreResponse> responseObserver) {
        String operatorId  = request.getOperatorId();
        String snapshotKey = request.getSnapshotObjectKey();
        String operatorType = request.getOperatorType();

        log.info("RestoreOperator: id={} type={} snapshot={}", operatorId, operatorType, snapshotKey);

        try {
            // Step 1: Download snapshot
            byte[] snapshotBytes = minioClient.downloadSnapshot(snapshotKey);

            // Step 2: Deserialize + translate
            Map<String, Object> rawState   = deserializer.deserialize(snapshotBytes, operatorType);
            Map<String, Object> flinkState = deserializer.translateToFlinkState(rawState, operatorType);

            // Step 3: Create MigratedOperator
            MigratedOperator operator = OperatorFactory.create(operatorId, operatorType, flinkState);

            // Step 4: Submit Flink job (simplified — real implementation uses Flink REST API)
            String jobId = submitFlinkJob(operatorId, operatorType, operator, request);
            operatorJobIds.put(operatorId, jobId);

            log.info("Restored operator {} as Flink job {}", operatorId, jobId);

            responseObserver.onNext(RestoreResponse.newBuilder()
                .setOperatorId(operatorId)
                .setJobId(jobId)
                .setSuccess(true)
                .build());

        } catch (Exception e) {
            log.error("Failed to restore operator {}: {}", operatorId, e.getMessage(), e);
            responseObserver.onNext(RestoreResponse.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg(e.getMessage())
                .build());
        }

        responseObserver.onCompleted();
    }

    /**
     * PCTR Phase 4 (cloud-side): Terminate a running Flink job when operator migrates back to edge.
     */
    @Override
    public void terminateOperator(TerminateRequest request, StreamObserver<TerminateAck> responseObserver) {
        String operatorId = request.getOperatorId();
        String jobId      = operatorJobIds.remove(operatorId);

        if (jobId == null) {
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg("No active Flink job found for operator " + operatorId)
                .build());
            responseObserver.onCompleted();
            return;
        }

        try {
            cancelFlinkJob(jobId);
            log.info("Terminated Flink job {} for operator {}", jobId, operatorId);
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(true)
                .build());
        } catch (Exception e) {
            log.error("Failed to terminate job {} for operator {}: {}", jobId, operatorId, e.getMessage());
            responseObserver.onNext(TerminateAck.newBuilder()
                .setOperatorId(operatorId)
                .setSuccess(false)
                .setErrorMsg(e.getMessage())
                .build());
        }

        responseObserver.onCompleted();
    }

    /**
     * Get status of a running Flink job for an operator.
     */
    @Override
    public void getJobStatus(JobStatusRequest request, StreamObserver<JobStatusResponse> responseObserver) {
        String operatorId = request.getOperatorId();
        String jobId = operatorJobIds.get(operatorId);
        String status;

        if (jobId == null) {
            status = "NOT_FOUND";
        } else {
            // TODO: Query Flink REST API for actual job status
            status = "RUNNING";  // Mock for now
        }

        responseObserver.onNext(JobStatusResponse.newBuilder()
            .setOperatorId(operatorId)
            .setJobId(jobId != null ? jobId : "")
            .setStatus(status)
            .build());
        
        responseObserver.onCompleted();
    }

    // ── Private Helpers ────────────────────────────────────────────────────────────────

    /**
     * Submit a Flink job for a migrated operator.
     * In a real deployment, this uses the Flink REST API (POST /jars/{id}/run).
     * For initial implementation, uses a mock job ID.
     */
    private String submitFlinkJob(
        String operatorId,
        String operatorType,
        MigratedOperator operator,
        RestoreRequest request
    ) {
        // TODO: Replace with actual Flink cluster submission via REST API
        // For now, return a mock job ID for testing
        String jobId = "flink-job-" + operatorId + "-" + System.currentTimeMillis();
        log.debug("Submitting Flink job: operator={} type={} jobId={}", operatorId, operatorType, jobId);
        return jobId;
    }

    private void cancelFlinkJob(String jobId) {
        // TODO: Use Flink REST API to cancel job: PATCH /jobs/{jobId}?mode=cancel
        log.debug("Cancelling Flink job: {}", jobId);
    }
}