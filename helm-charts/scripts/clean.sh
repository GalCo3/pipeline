#!/usr/bin/env bash
# Wipes all pipeline data: Elasticsearch indices, Kafka topics and consumer
# groups, MongoDB databases, and MinIO buckets. Infrastructure stays up;
# re-run scripts/install.sh (or the es-index job) to recreate the index.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"

if [[ "${1:-}" != "--yes" ]]; then
    echo "This deletes ALL data in namespace '$NAMESPACE':"
    echo "  - every non-system Elasticsearch index"
    echo "  - every non-internal Kafka topic and consumer group"
    echo "  - every non-system MongoDB database"
    echo "  - every MinIO bucket"
    read -r -p "Continue? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

pod() {
    kubectl -n "$NAMESPACE" get pods -l "app.kubernetes.io/name=$1" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null \
    || kubectl -n "$NAMESPACE" get pods -o name | grep -m1 "$1" | cut -d/ -f2
}

echo "==> Stopping consumers"
kubectl -n "$NAMESPACE" scale deploy/cargo-lexical --replicas=0 2>/dev/null || true

echo "==> Elasticsearch: deleting indices"
ES_POD="$(pod elasticsearch)"
for index in $(kubectl -n "$NAMESPACE" exec "$ES_POD" -- \
        curl -s "localhost:9200/_cat/indices?h=index" | grep -v '^\.'); do
    echo "    $index"
    kubectl -n "$NAMESPACE" exec "$ES_POD" -- \
        curl -s -X DELETE "localhost:9200/$index" >/dev/null
done

echo "==> Kafka: deleting topics and consumer groups"
KAFKA_POD="$(pod kafka)"
kafka_cli() {
    kubectl -n "$NAMESPACE" exec "$KAFKA_POD" -- \
        sh -c "PATH=\$PATH:/opt/bitnami/kafka/bin:/opt/kafka/bin; $*"
}
for topic in $(kafka_cli "kafka-topics.sh --bootstrap-server localhost:9092 --list" | grep -v '^__'); do
    echo "    topic $topic"
    kafka_cli "kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic $topic"
done
for group in $(kafka_cli "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list"); do
    echo "    group $group"
    kafka_cli "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --delete --group $group" || true
done

echo "==> MongoDB: dropping databases"
MONGO_POD="$(pod mongodb)"
kubectl -n "$NAMESPACE" exec "$MONGO_POD" -- mongosh --quiet \
    -u root -p mongoadmin --authenticationDatabase admin --eval '
    db.adminCommand({listDatabases: 1}).databases
      .map(d => d.name)
      .filter(n => !["admin", "config", "local"].includes(n))
      .forEach(n => { print("    " + n); db.getSiblingDB(n).dropDatabase(); });'

echo "==> MinIO: deleting buckets"
MINIO_POD="$(pod minio)"
kubectl -n "$NAMESPACE" exec "$MINIO_POD" -- sh -c '
    mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null
    for bucket in $(mc ls local --json | sed -n "s/.*\"key\":\"\([^\"]*\)\/\".*/\1/p"); do
        echo "    $bucket"
        mc rb --force "local/$bucket" >/dev/null
    done'

echo "==> Restarting consumers"
kubectl -n "$NAMESPACE" scale deploy/cargo-lexical --replicas=1 2>/dev/null || true

echo "Done. Re-run the es-index job (scripts/install.sh) before producing again."
