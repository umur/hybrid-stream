FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# Copy proto files first
COPY proto/ /build/proto/

# Copy pom.xml and download dependencies
COPY flink-connector/pom.xml /build/
RUN mvn dependency:go-offline -B

# Copy source and build
COPY flink-connector/ /build/
RUN mvn package -DskipTests -B -q

FROM eclipse-temurin:21-jre-jammy

WORKDIR /app

# Copy built JAR
COPY --from=builder /build/target/*-with-dependencies.jar /app/app.jar

# Copy schema registry files
RUN mkdir -p /app/schemas
COPY schema-registry/schemas/ /app/schemas/

# Create data directories
RUN mkdir -p /app/data

EXPOSE 50053

ENTRYPOINT ["java", "-Xms512m", "-Xmx2g", "-jar", "/app/app.jar"]