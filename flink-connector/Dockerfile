# Build stage
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# Copy proto files to the expected location (pom.xml expects ../proto from /build)
COPY proto/ /proto/
COPY flink-connector/pom.xml /build/pom.xml

# Download deps first (layer cache)
RUN mvn dependency:go-offline -B -q

# Copy source and build  
COPY flink-connector/src/ /build/src/
RUN mvn package -DskipTests -B -q

# Runtime stage
FROM eclipse-temurin:21-jre-jammy

WORKDIR /app

# Copy the shaded jar (maven-shade-plugin produces artifact-version.jar with all deps)
COPY --from=builder /build/target/hybridstream-flink-connector-0.1.0.jar /app/app.jar

# Schema files (context is repo root)
COPY schema-registry/schemas/ /app/schemas/

RUN mkdir -p /app/data

EXPOSE 50053

ENTRYPOINT ["java", "-Xms512m", "-Xmx2g", "-jar", "/app/app.jar"]