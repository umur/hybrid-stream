package ai.hybridstream.proto;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 */
@javax.annotation.Generated(
    value = "by gRPC proto compiler (version 1.58.0)",
    comments = "Source: hybridstream.proto")
@io.grpc.stub.annotations.GrpcGenerated
public final class FlinkConnectorGrpc {

  private FlinkConnectorGrpc() {}

  public static final java.lang.String SERVICE_NAME = "hybridstream.v1.FlinkConnector";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.RestoreRequest,
      ai.hybridstream.proto.RestoreResponse> getRestoreOperatorMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "RestoreOperator",
      requestType = ai.hybridstream.proto.RestoreRequest.class,
      responseType = ai.hybridstream.proto.RestoreResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.RestoreRequest,
      ai.hybridstream.proto.RestoreResponse> getRestoreOperatorMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.RestoreRequest, ai.hybridstream.proto.RestoreResponse> getRestoreOperatorMethod;
    if ((getRestoreOperatorMethod = FlinkConnectorGrpc.getRestoreOperatorMethod) == null) {
      synchronized (FlinkConnectorGrpc.class) {
        if ((getRestoreOperatorMethod = FlinkConnectorGrpc.getRestoreOperatorMethod) == null) {
          FlinkConnectorGrpc.getRestoreOperatorMethod = getRestoreOperatorMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.RestoreRequest, ai.hybridstream.proto.RestoreResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "RestoreOperator"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.RestoreRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.RestoreResponse.getDefaultInstance()))
              .setSchemaDescriptor(new FlinkConnectorMethodDescriptorSupplier("RestoreOperator"))
              .build();
        }
      }
    }
    return getRestoreOperatorMethod;
  }

  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.TerminateRequest,
      ai.hybridstream.proto.TerminateAck> getTerminateOperatorMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "TerminateOperator",
      requestType = ai.hybridstream.proto.TerminateRequest.class,
      responseType = ai.hybridstream.proto.TerminateAck.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.TerminateRequest,
      ai.hybridstream.proto.TerminateAck> getTerminateOperatorMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.TerminateRequest, ai.hybridstream.proto.TerminateAck> getTerminateOperatorMethod;
    if ((getTerminateOperatorMethod = FlinkConnectorGrpc.getTerminateOperatorMethod) == null) {
      synchronized (FlinkConnectorGrpc.class) {
        if ((getTerminateOperatorMethod = FlinkConnectorGrpc.getTerminateOperatorMethod) == null) {
          FlinkConnectorGrpc.getTerminateOperatorMethod = getTerminateOperatorMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.TerminateRequest, ai.hybridstream.proto.TerminateAck>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "TerminateOperator"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TerminateRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TerminateAck.getDefaultInstance()))
              .setSchemaDescriptor(new FlinkConnectorMethodDescriptorSupplier("TerminateOperator"))
              .build();
        }
      }
    }
    return getTerminateOperatorMethod;
  }

  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.JobStatusRequest,
      ai.hybridstream.proto.JobStatusResponse> getGetJobStatusMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetJobStatus",
      requestType = ai.hybridstream.proto.JobStatusRequest.class,
      responseType = ai.hybridstream.proto.JobStatusResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.JobStatusRequest,
      ai.hybridstream.proto.JobStatusResponse> getGetJobStatusMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.JobStatusRequest, ai.hybridstream.proto.JobStatusResponse> getGetJobStatusMethod;
    if ((getGetJobStatusMethod = FlinkConnectorGrpc.getGetJobStatusMethod) == null) {
      synchronized (FlinkConnectorGrpc.class) {
        if ((getGetJobStatusMethod = FlinkConnectorGrpc.getGetJobStatusMethod) == null) {
          FlinkConnectorGrpc.getGetJobStatusMethod = getGetJobStatusMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.JobStatusRequest, ai.hybridstream.proto.JobStatusResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetJobStatus"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.JobStatusRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.JobStatusResponse.getDefaultInstance()))
              .setSchemaDescriptor(new FlinkConnectorMethodDescriptorSupplier("GetJobStatus"))
              .build();
        }
      }
    }
    return getGetJobStatusMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static FlinkConnectorStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorStub>() {
        @java.lang.Override
        public FlinkConnectorStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new FlinkConnectorStub(channel, callOptions);
        }
      };
    return FlinkConnectorStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static FlinkConnectorBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorBlockingStub>() {
        @java.lang.Override
        public FlinkConnectorBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new FlinkConnectorBlockingStub(channel, callOptions);
        }
      };
    return FlinkConnectorBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static FlinkConnectorFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<FlinkConnectorFutureStub>() {
        @java.lang.Override
        public FlinkConnectorFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new FlinkConnectorFutureStub(channel, callOptions);
        }
      };
    return FlinkConnectorFutureStub.newStub(factory, channel);
  }

  /**
   */
  public interface AsyncService {

    /**
     */
    default void restoreOperator(ai.hybridstream.proto.RestoreRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.RestoreResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getRestoreOperatorMethod(), responseObserver);
    }

    /**
     */
    default void terminateOperator(ai.hybridstream.proto.TerminateRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getTerminateOperatorMethod(), responseObserver);
    }

    /**
     */
    default void getJobStatus(ai.hybridstream.proto.JobStatusRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.JobStatusResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetJobStatusMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service FlinkConnector.
   */
  public static abstract class FlinkConnectorImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return FlinkConnectorGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service FlinkConnector.
   */
  public static final class FlinkConnectorStub
      extends io.grpc.stub.AbstractAsyncStub<FlinkConnectorStub> {
    private FlinkConnectorStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected FlinkConnectorStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new FlinkConnectorStub(channel, callOptions);
    }

    /**
     */
    public void restoreOperator(ai.hybridstream.proto.RestoreRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.RestoreResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getRestoreOperatorMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     */
    public void terminateOperator(ai.hybridstream.proto.TerminateRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getTerminateOperatorMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     */
    public void getJobStatus(ai.hybridstream.proto.JobStatusRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.JobStatusResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetJobStatusMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service FlinkConnector.
   */
  public static final class FlinkConnectorBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<FlinkConnectorBlockingStub> {
    private FlinkConnectorBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected FlinkConnectorBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new FlinkConnectorBlockingStub(channel, callOptions);
    }

    /**
     */
    public ai.hybridstream.proto.RestoreResponse restoreOperator(ai.hybridstream.proto.RestoreRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getRestoreOperatorMethod(), getCallOptions(), request);
    }

    /**
     */
    public ai.hybridstream.proto.TerminateAck terminateOperator(ai.hybridstream.proto.TerminateRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getTerminateOperatorMethod(), getCallOptions(), request);
    }

    /**
     */
    public ai.hybridstream.proto.JobStatusResponse getJobStatus(ai.hybridstream.proto.JobStatusRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetJobStatusMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service FlinkConnector.
   */
  public static final class FlinkConnectorFutureStub
      extends io.grpc.stub.AbstractFutureStub<FlinkConnectorFutureStub> {
    private FlinkConnectorFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected FlinkConnectorFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new FlinkConnectorFutureStub(channel, callOptions);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.RestoreResponse> restoreOperator(
        ai.hybridstream.proto.RestoreRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getRestoreOperatorMethod(), getCallOptions()), request);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.TerminateAck> terminateOperator(
        ai.hybridstream.proto.TerminateRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getTerminateOperatorMethod(), getCallOptions()), request);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.JobStatusResponse> getJobStatus(
        ai.hybridstream.proto.JobStatusRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetJobStatusMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_RESTORE_OPERATOR = 0;
  private static final int METHODID_TERMINATE_OPERATOR = 1;
  private static final int METHODID_GET_JOB_STATUS = 2;

  private static final class MethodHandlers<Req, Resp> implements
      io.grpc.stub.ServerCalls.UnaryMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ServerStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ClientStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.BidiStreamingMethod<Req, Resp> {
    private final AsyncService serviceImpl;
    private final int methodId;

    MethodHandlers(AsyncService serviceImpl, int methodId) {
      this.serviceImpl = serviceImpl;
      this.methodId = methodId;
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public void invoke(Req request, io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        case METHODID_RESTORE_OPERATOR:
          serviceImpl.restoreOperator((ai.hybridstream.proto.RestoreRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.RestoreResponse>) responseObserver);
          break;
        case METHODID_TERMINATE_OPERATOR:
          serviceImpl.terminateOperator((ai.hybridstream.proto.TerminateRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck>) responseObserver);
          break;
        case METHODID_GET_JOB_STATUS:
          serviceImpl.getJobStatus((ai.hybridstream.proto.JobStatusRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.JobStatusResponse>) responseObserver);
          break;
        default:
          throw new AssertionError();
      }
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public io.grpc.stub.StreamObserver<Req> invoke(
        io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        default:
          throw new AssertionError();
      }
    }
  }

  public static final io.grpc.ServerServiceDefinition bindService(AsyncService service) {
    return io.grpc.ServerServiceDefinition.builder(getServiceDescriptor())
        .addMethod(
          getRestoreOperatorMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.RestoreRequest,
              ai.hybridstream.proto.RestoreResponse>(
                service, METHODID_RESTORE_OPERATOR)))
        .addMethod(
          getTerminateOperatorMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.TerminateRequest,
              ai.hybridstream.proto.TerminateAck>(
                service, METHODID_TERMINATE_OPERATOR)))
        .addMethod(
          getGetJobStatusMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.JobStatusRequest,
              ai.hybridstream.proto.JobStatusResponse>(
                service, METHODID_GET_JOB_STATUS)))
        .build();
  }

  private static abstract class FlinkConnectorBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    FlinkConnectorBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return ai.hybridstream.proto.HybridStreamProto.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("FlinkConnector");
    }
  }

  private static final class FlinkConnectorFileDescriptorSupplier
      extends FlinkConnectorBaseDescriptorSupplier {
    FlinkConnectorFileDescriptorSupplier() {}
  }

  private static final class FlinkConnectorMethodDescriptorSupplier
      extends FlinkConnectorBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    FlinkConnectorMethodDescriptorSupplier(java.lang.String methodName) {
      this.methodName = methodName;
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.MethodDescriptor getMethodDescriptor() {
      return getServiceDescriptor().findMethodByName(methodName);
    }
  }

  private static volatile io.grpc.ServiceDescriptor serviceDescriptor;

  public static io.grpc.ServiceDescriptor getServiceDescriptor() {
    io.grpc.ServiceDescriptor result = serviceDescriptor;
    if (result == null) {
      synchronized (FlinkConnectorGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new FlinkConnectorFileDescriptorSupplier())
              .addMethod(getRestoreOperatorMethod())
              .addMethod(getTerminateOperatorMethod())
              .addMethod(getGetJobStatusMethod())
              .build();
        }
      }
    }
    return result;
  }
}
