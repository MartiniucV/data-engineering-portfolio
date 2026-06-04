#!/usr/bin/env bash
# Start a single-node Kafka broker (KRaft mode — no Zookeeper) using Docker
# and create the "orders" topic for the Spark Structured Streaming job.
#
# KRaft mode: Kafka manages its own metadata without Zookeeper (stable since Kafka 3.3).
# This matches the kafka_streaming/ project's docker-compose setup.
set -euo pipefail

CONTAINER="kafka-for-spark"
IMAGE="confluentinc/cp-kafka:7.6.1"
TOPIC="orders"
PORT=9092
# Deterministic cluster ID required for KRaft mode
CLUSTER_ID="MkU3OEVBNTcwNTJENDM2Qg=="

echo "──────────────────────────────────────────────"
echo "  Starting Kafka broker (KRaft, no Zookeeper)"
echo "──────────────────────────────────────────────"

# Stop and remove existing container if present
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Removing existing container: ${CONTAINER}"
    docker stop "${CONTAINER}" 2>/dev/null || true
    docker rm   "${CONTAINER}" 2>/dev/null || true
fi

docker run -d \
    --name "${CONTAINER}" \
    -p "${PORT}:${PORT}" \
    -e KAFKA_NODE_ID=1 \
    -e KAFKA_PROCESS_ROLES="broker,controller" \
    -e KAFKA_CONTROLLER_QUORUM_VOTERS="1@localhost:29093" \
    -e KAFKA_LISTENERS="PLAINTEXT://0.0.0.0:${PORT},CONTROLLER://0.0.0.0:29093" \
    -e KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://localhost:${PORT}" \
    -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT" \
    -e KAFKA_CONTROLLER_LISTENER_NAMES="CONTROLLER" \
    -e KAFKA_INTER_BROKER_LISTENER_NAME="PLAINTEXT" \
    -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
    -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
    -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
    -e KAFKA_LOG_RETENTION_HOURS=24 \
    -e CLUSTER_ID="${CLUSTER_ID}" \
    "${IMAGE}"

echo "Waiting for Kafka to initialise (15 s)..."
sleep 15

echo "Creating topic: ${TOPIC} (3 partitions)"
docker exec "${CONTAINER}" \
    kafka-topics \
    --create \
    --topic "${TOPIC}" \
    --bootstrap-server "localhost:${PORT}" \
    --replication-factor 1 \
    --partitions 3 \
    --if-not-exists

echo ""
echo "Topic list:"
docker exec "${CONTAINER}" \
    kafka-topics --list --bootstrap-server "localhost:${PORT}"

echo ""
echo "✓  Kafka ready on localhost:${PORT}"
echo ""
echo "Next steps:"
echo "  1. In a separate terminal, start the order producer:"
echo "     cd ../kafka_streaming && python producer.py"
echo ""
echo "  2. Then start the Spark streaming job:"
echo "     python streaming_job.py"
echo ""
echo "To stop Kafka:"
echo "  docker stop ${CONTAINER} && docker rm ${CONTAINER}"
