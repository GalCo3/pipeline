#!/usr/bin/env bash
# Wipes all pipeline data: Elasticsearch indices, Kafka topics and consumer
# groups, MongoDB databases, MinIO buckets, and the telemetry Grafana reads —
# Loki logs, Mimir metrics and Tempo traces. Grafana's own volume is left alone:
# it holds dashboards and preferences, not collected data.
# Infrastructure stays up; run tools/scripts/populate.sh to recreate the indices and
# re-produce the examples.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"

if [[ "${1:-}" != "--yes" ]]; then
    echo "This deletes ALL data in namespace '$NAMESPACE':"
    echo "  - every non-system Elasticsearch index"
    echo "  - every non-internal Kafka topic and consumer group"
    echo "  - every non-system MongoDB database"
    echo "  - every MinIO bucket"
    echo "  - all Loki logs, Mimir metrics and Tempo traces"
    read -r -p "Continue? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

pod() {
    kubectl -n "$NAMESPACE" get pods -l "app.kubernetes.io/name=$1" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null \
    || kubectl -n "$NAMESPACE" get pods -o name | grep -m1 "$1" | cut -d/ -f2
}

# Every infra pod here has a sidecar or init container, so name the app container
# explicitly — otherwise kubectl prints a "Defaulted container" line per exec.
in_pod() {
    local name="$1"
    shift
    kubectl -n "$NAMESPACE" exec "$(pod "$name")" -c "$name" -- "$@"
}

# Every consumer deployment: a live member keeps its consumer group non-empty,
# which makes the group deletion below fail. The semantic consumers belong here
# as much as the lexical ones — left running, they hold a subscription to a
# topic this script deletes, and rejoin the recreated topic with no partitions
# assigned, so they silently consume nothing until something restarts them.
CONSUMERS=(candy-lexical cargo-operational-lexical cargo-my-storage-lexical chat-messages-lexical chat-rooms-lexical chat-users-lexical chief-lexical cargo-operational-semantic cargo-my-storage-semantic chief-semantic)

echo "==> Stopping consumers"
for consumer in "${CONSUMERS[@]}"; do
    kubectl -n "$NAMESPACE" scale "deploy/$consumer" --replicas=0 2>/dev/null || true
done
# In parallel: serial waits would add up to one termination grace period each.
for consumer in "${CONSUMERS[@]}"; do
    kubectl -n "$NAMESPACE" wait --for=delete pod \
        -l "app.kubernetes.io/name=$consumer" --timeout=60s >/dev/null 2>&1 &
done
wait

echo "==> Elasticsearch: deleting indices"
for index in $(in_pod elasticsearch curl -s "localhost:9200/_cat/indices?h=index" | grep -v '^\.'); do
    echo "    $index"
    in_pod elasticsearch curl -s -X DELETE "localhost:9200/$index" >/dev/null
done

echo "==> Kafka: deleting topics and consumer groups"
kafka_cli() {
    in_pod kafka sh -c "PATH=\$PATH:/opt/bitnami/kafka/bin:/opt/kafka/bin; $*"
}

for topic in $(kafka_cli "kafka-topics.sh --bootstrap-server localhost:9092 --list" | grep -v '^__'); do
    echo "    topic $topic"
    kafka_cli "kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic $topic"
done

# One exec for every group, not one per group. A consumer killed by SIGKILL never
# sends LeaveGroup, so the broker holds its member until session.timeout.ms (60s)
# expires and the delete fails with GroupNotEmptyException. Not worth waiting out:
# the group's offsets died with the topic above, so a leftover group is an empty
# shell the consumer re-registers against on its next start.
groups="$(kafka_cli "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list" | tr -d '\r' | tr '\n' ' ')"
if [[ -n "${groups// /}" ]]; then
    echo "    groups $groups"
    delete_args=""
    for group in $groups; do
        delete_args="$delete_args --group $group"
    done
    kafka_cli "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --delete $delete_args" >/dev/null 2>&1 \
        || echo "        some groups still had live members; left in place (offsets are gone with their topics)"
fi

echo "==> MongoDB: dropping databases"
in_pod mongodb mongosh --quiet \
    -u root -p mongoadmin --authenticationDatabase admin --eval '
    db.adminCommand({listDatabases: 1}).databases
      .map(d => d.name)
      .filter(n => !["admin", "config", "local"].includes(n))
      .forEach(n => { print("    " + n); db.getSiblingDB(n).dropDatabase(); });'

echo "==> MinIO: deleting buckets"
in_pod minio sh -c '
    mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null
    for bucket in $(mc ls local --json | sed -n "s/.*\"key\":\"\([^\"]*\)\/\".*/\1/p"); do
        echo "    $bucket"
        mc rb --force "local/$bucket" >/dev/null
    done'

# Loki, Mimir and Tempo each keep everything under /data on a ReadWriteOnce
# claim named after the release. None of them offers a delete API worth using
# here — Tempo has none at all — so the volume is emptied directly.
#
# It has to happen with the pod stopped. All three flush their in-memory
# ingester to disk on shutdown, so deleting the files from under a running
# process just gets them written straight back on the next restart.
#
# The wipe runs in a throwaway pod, which is the only way into the claim once
# its owner is gone. It uses curlimages/curl, already small and simple enough
# to need no build of its own, and the same UID as the charts, since the files
# it has to unlink are owned by 10001.
wipe_telemetry() {
    local release="$1"

    echo "    $release"
    kubectl -n "$NAMESPACE" scale "deploy/$release" --replicas=0 >/dev/null
    kubectl -n "$NAMESPACE" wait --for=delete pod \
        -l "app.kubernetes.io/name=$release" --timeout=120s >/dev/null 2>&1 || true

    kubectl -n "$NAMESPACE" delete pod "wipe-$release" --ignore-not-found >/dev/null
    kubectl -n "$NAMESPACE" apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: wipe-$release
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: wipe
      image: docker.io/curlimages/curl:8.11.1
      # An empty /data leaves the globs unexpanded and rm complains; the exit
      # status is forced so a nothing-to-do wipe still counts as success.
      command: ["sh", "-c", "rm -rf /data/* /data/.[!.]* 2>/dev/null; true"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: $release
EOF
    kubectl -n "$NAMESPACE" wait --for=jsonpath='{.status.phase}'=Succeeded \
        "pod/wipe-$release" --timeout=120s >/dev/null
    kubectl -n "$NAMESPACE" delete pod "wipe-$release" --ignore-not-found >/dev/null

    kubectl -n "$NAMESPACE" scale "deploy/$release" --replicas=1 >/dev/null
}

# The collector keeps pushing throughout, so a little telemetry from the rest of
# the namespace lands again as soon as each one is back. That is the stack
# reporting on itself, not leftover pipeline data.
echo "==> Grafana stack: deleting logs, metrics and traces"
for release in loki mimir tempo; do
    wipe_telemetry "$release"
done

# The consumers stay down. Their topics were just deleted, and a consumer
# subscribed to a topic that no longer exists dies on UNKNOWN_TOPIC_OR_PART;
# their memory requests would also leave the single dev node with no room for
# the demo-producer job pod to schedule into. tools/scripts/populate.sh
# produces the examples and starts them again.
echo
echo "Done. Consumers are stopped — run tools/scripts/populate.sh to re-produce"
echo "the examples and start them."
