package ai.hybridstream.proto;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 */
@javax.annotation.Generated(
    value = "by gRPC proto compiler (version 1.58.0)",
    comments = "Source: hybridstream.proto")
@io.grpc.stub.annotations.GrpcGenerated
public final class HEAManagementGrpc {

  private HEAManagementGrpc() {}

  public static final java.lang.String SERVICE_NAME = "hybridstream.v1.HEAManagement";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.TelemetryRequest,
      ai.hybridstream.proto.TelemetryResponse> getGetTelemetryMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetTelemetry",
      requestType = ai.hybridstream.proto.TelemetryRequest.class,
      responseType = ai.hybridstream.proto.TelemetryResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.TelemetryRequest,
      ai.hybridstream.proto.TelemetryResponse> getGetTelemetryMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.TelemetryRequest, ai.hybridstream.proto.TelemetryResponse> getGetTelemetryMethod;
    if ((getGetTelemetryMethod = HEAManagementGrpc.getGetTelemetryMethod) == null) {
      synchronized (HEAManagementGrpc.class) {
        if ((getGetTelemetryMethod = HEAManagementGrpc.getGetTelemetryMethod) == null) {
          HEAManagementGrpc.getGetTelemetryMethod = getGetTelemetryMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.TelemetryRequest, ai.hybridstream.proto.TelemetryResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetTelemetry"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TelemetryRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TelemetryResponse.getDefaultInstance()))
              .setSchemaDescriptor(new HEAManagementMethodDescriptorSupplier("GetTelemetry"))
              .build();
        }
      }
    }
    return getGetTelemetryMethod;
  }

  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.PlacementDirective,
      ai.hybridstream.proto.PlacementAck> getApplyPlacementMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ApplyPlacement",
      requestType = ai.hybridstream.proto.PlacementDirective.class,
      responseType = ai.hybridstream.proto.PlacementAck.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.PlacementDirective,
      ai.hybridstream.proto.PlacementAck> getApplyPlacementMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.PlacementDirective, ai.hybridstream.proto.PlacementAck> getApplyPlacementMethod;
    if ((getApplyPlacementMethod = HEAManagementGrpc.getApplyPlacementMethod) == null) {
      synchronized (HEAManagementGrpc.class) {
        if ((getApplyPlacementMethod = HEAManagementGrpc.getApplyPlacementMethod) == null) {
          HEAManagementGrpc.getApplyPlacementMethod = getApplyPlacementMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.PlacementDirective, ai.hybridstream.proto.PlacementAck>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ApplyPlacement"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.PlacementDirective.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.PlacementAck.getDefaultInstance()))
              .setSchemaDescriptor(new HEAManagementMethodDescriptorSupplier("ApplyPlacement"))
              .build();
        }
      }
    }
    return getApplyPlacementMethod;
  }

  private static volatile io.grpc.MethodDescriptor<ai.hybridstream.proto.SnapshotRequest,
      ai.hybridstream.proto.SnapshotResponse> getTriggerSnapshotMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "TriggerSnapshot",
      requestType = ai.hybridstream.proto.SnapshotRequest.class,
      responseType = ai.hybridstream.proto.SnapshotResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<ai.hybridstream.proto.SnapshotRequest,
      ai.hybridstream.proto.SnapshotResponse> getTriggerSnapshotMethod() {
    io.grpc.MethodDescriptor<ai.hybridstream.proto.SnapshotRequest, ai.hybridstream.proto.SnapshotResponse> getTriggerSnapshotMethod;
    if ((getTriggerSnapshotMethod = HEAManagementGrpc.getTriggerSnapshotMethod) == null) {
      synchronized (HEAManagementGrpc.class) {
        if ((getTriggerSnapshotMethod = HEAManagementGrpc.getTriggerSnapshotMethod) == null) {
          HEAManagementGrpc.getTriggerSnapshotMethod = getTriggerSnapshotMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.SnapshotRequest, ai.hybridstream.proto.SnapshotResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "TriggerSnapshot"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.SnapshotRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.SnapshotResponse.getDefaultInstance()))
              .setSchemaDescriptor(new HEAManagementMethodDescriptorSupplier("TriggerSnapshot"))
              .build();
        }
      }
    }
    return getTriggerSnapshotMethod;
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
    if ((getTerminateOperatorMethod = HEAManagementGrpc.getTerminateOperatorMethod) == null) {
      synchronized (HEAManagementGrpc.class) {
        if ((getTerminateOperatorMethod = HEAManagementGrpc.getTerminateOperatorMethod) == null) {
          HEAManagementGrpc.getTerminateOperatorMethod = getTerminateOperatorMethod =
              io.grpc.MethodDescriptor.<ai.hybridstream.proto.TerminateRequest, ai.hybridstream.proto.TerminateAck>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "TerminateOperator"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TerminateRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  ai.hybridstream.proto.TerminateAck.getDefaultInstance()))
              .setSchemaDescriptor(new HEAManagementMethodDescriptorSupplier("TerminateOperator"))
              .build();
        }
      }
    }
    return getTerminateOperatorMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static HEAManagementStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<HEAManagementStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<HEAManagementStub>() {
        @java.lang.Override
        public HEAManagementStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new HEAManagementStub(channel, callOptions);
        }
      };
    return HEAManagementStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static HEAManagementBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<HEAManagementBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<HEAManagementBlockingStub>() {
        @java.lang.Override
        public HEAManagementBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new HEAManagementBlockingStub(channel, callOptions);
        }
      };
    return HEAManagementBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static HEAManagementFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<HEAManagementFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<HEAManagementFutureStub>() {
        @java.lang.Override
        public HEAManagementFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new HEAManagementFutureStub(channel, callOptions);
        }
      };
    return HEAManagementFutureStub.newStub(factory, channel);
  }

  /**
   */
  public interface AsyncService {

    /**
     */
    default void getTelemetry(ai.hybridstream.proto.TelemetryRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TelemetryResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetTelemetryMethod(), responseObserver);
    }

    /**
     */
    default void applyPlacement(ai.hybridstream.proto.PlacementDirective request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.PlacementAck> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getApplyPlacementMethod(), responseObserver);
    }

    /**
     */
    default void triggerSnapshot(ai.hybridstream.proto.SnapshotRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.SnapshotResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getTriggerSnapshotMethod(), responseObserver);
    }

    /**
     */
    default void terminateOperator(ai.hybridstream.proto.TerminateRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getTerminateOperatorMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service HEAManagement.
   */
  public static abstract class HEAManagementImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return HEAManagementGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service HEAManagement.
   */
  public static final class HEAManagementStub
      extends io.grpc.stub.AbstractAsyncStub<HEAManagementStub> {
    private HEAManagementStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected HEAManagementStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new HEAManagementStub(channel, callOptions);
    }

    /**
     */
    public void getTelemetry(ai.hybridstream.proto.TelemetryRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TelemetryResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetTelemetryMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     */
    public void applyPlacement(ai.hybridstream.proto.PlacementDirective request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.PlacementAck> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getApplyPlacementMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     */
    public void triggerSnapshot(ai.hybridstream.proto.SnapshotRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.SnapshotResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getTriggerSnapshotMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     */
    public void terminateOperator(ai.hybridstream.proto.TerminateRequest request,
        io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getTerminateOperatorMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service HEAManagement.
   */
  public static final class HEAManagementBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<HEAManagementBlockingStub> {
    private HEAManagementBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected HEAManagementBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new HEAManagementBlockingStub(channel, callOptions);
    }

    /**
     */
    public ai.hybridstream.proto.TelemetryResponse getTelemetry(ai.hybridstream.proto.TelemetryRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetTelemetryMethod(), getCallOptions(), request);
    }

    /**
     */
    public ai.hybridstream.proto.PlacementAck applyPlacement(ai.hybridstream.proto.PlacementDirective request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getApplyPlacementMethod(), getCallOptions(), request);
    }

    /**
     */
    public ai.hybridstream.proto.SnapshotResponse triggerSnapshot(ai.hybridstream.proto.SnapshotRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getTriggerSnapshotMethod(), getCallOptions(), request);
    }

    /**
     */
    public ai.hybridstream.proto.TerminateAck terminateOperator(ai.hybridstream.proto.TerminateRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getTerminateOperatorMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service HEAManagement.
   */
  public static final class HEAManagementFutureStub
      extends io.grpc.stub.AbstractFutureStub<HEAManagementFutureStub> {
    private HEAManagementFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected HEAManagementFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new HEAManagementFutureStub(channel, callOptions);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.TelemetryResponse> getTelemetry(
        ai.hybridstream.proto.TelemetryRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetTelemetryMethod(), getCallOptions()), request);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.PlacementAck> applyPlacement(
        ai.hybridstream.proto.PlacementDirective request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getApplyPlacementMethod(), getCallOptions()), request);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.SnapshotResponse> triggerSnapshot(
        ai.hybridstream.proto.SnapshotRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getTriggerSnapshotMethod(), getCallOptions()), request);
    }

    /**
     */
    public com.google.common.util.concurrent.ListenableFuture<ai.hybridstream.proto.TerminateAck> terminateOperator(
        ai.hybridstream.proto.TerminateRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getTerminateOperatorMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_GET_TELEMETRY = 0;
  private static final int METHODID_APPLY_PLACEMENT = 1;
  private static final int METHODID_TRIGGER_SNAPSHOT = 2;
  private static final int METHODID_TERMINATE_OPERATOR = 3;

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
        case METHODID_GET_TELEMETRY:
          serviceImpl.getTelemetry((ai.hybridstream.proto.TelemetryRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.TelemetryResponse>) responseObserver);
          break;
        case METHODID_APPLY_PLACEMENT:
          serviceImpl.applyPlacement((ai.hybridstream.proto.PlacementDirective) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.PlacementAck>) responseObserver);
          break;
        case METHODID_TRIGGER_SNAPSHOT:
          serviceImpl.triggerSnapshot((ai.hybridstream.proto.SnapshotRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.SnapshotResponse>) responseObserver);
          break;
        case METHODID_TERMINATE_OPERATOR:
          serviceImpl.terminateOperator((ai.hybridstream.proto.TerminateRequest) request,
              (io.grpc.stub.StreamObserver<ai.hybridstream.proto.TerminateAck>) responseObserver);
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
          getGetTelemetryMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.TelemetryRequest,
              ai.hybridstream.proto.TelemetryResponse>(
                service, METHODID_GET_TELEMETRY)))
        .addMethod(
          getApplyPlacementMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.PlacementDirective,
              ai.hybridstream.proto.PlacementAck>(
                service, METHODID_APPLY_PLACEMENT)))
        .addMethod(
          getTriggerSnapshotMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.SnapshotRequest,
              ai.hybridstream.proto.SnapshotResponse>(
                service, METHODID_TRIGGER_SNAPSHOT)))
        .addMethod(
          getTerminateOperatorMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              ai.hybridstream.proto.TerminateRequest,
              ai.hybridstream.proto.TerminateAck>(
                service, METHODID_TERMINATE_OPERATOR)))
        .build();
  }

  private static abstract class HEAManagementBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    HEAManagementBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return ai.hybridstream.proto.HybridStreamProto.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("HEAManagement");
    }
  }

  private static final class HEAManagementFileDescriptorSupplier
      extends HEAManagementBaseDescriptorSupplier {
    HEAManagementFileDescriptorSupplier() {}
  }

  private static final class HEAManagementMethodDescriptorSupplier
      extends HEAManagementBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    HEAManagementMethodDescriptorSupplier(java.lang.String methodName) {
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
      synchronized (HEAManagementGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new HEAManagementFileDescriptorSupplier())
              .addMethod(getGetTelemetryMethod())
              .addMethod(getApplyPlacementMethod())
              .addMethod(getTriggerSnapshotMethod())
              .addMethod(getTerminateOperatorMethod())
              .build();
        }
      }
    }
    return result;
  }
}
