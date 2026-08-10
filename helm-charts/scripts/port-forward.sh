#!/usr/bin/env bash
# Forwards every UI and API to localhost. Ctrl-C stops all of them.
#
# Docker Desktop's Kubernetes node is not reachable on the host network, so
# NodePort/LoadBalancer addresses do not resolve — port-forward is the way in.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
PIDS=()

forward() {
    local name="$1" svc="$2" local_port="$3" remote_port="$4"
    # kubectl exits immediately when the local port is taken, and its error
    # goes to /dev/null with everything else — so say so here instead.
    if lsof -nP -iTCP:"$local_port" -sTCP:LISTEN >/dev/null 2>&1; then
        printf '  %-16s SKIPPED — localhost:%s is already in use\n' "$name" "$local_port"
        return
    fi
    kubectl -n "$NAMESPACE" port-forward "svc/$svc" "$local_port:$remote_port" >/dev/null 2>&1 &
    PIDS+=("$!")
    printf '  %-16s http://localhost:%s\n' "$name" "$local_port"
}

cleanup() {
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

echo "Forwarding (Ctrl-C to stop):"
forward "grafana"       grafana       3000 3000
forward "mimir"         mimir         8090 8080
forward "loki"          loki          3100 3100
forward "tempo"         tempo         3200 3200
forward "kafka-ui"      kafka-ui      8080 8080
forward "kibana"        kibana        5601 5601
forward "headlamp"      headlamp      8081 80
forward "minio console" minio-console 9001 9090
forward "minio s3"      minio         9000 9000
forward "elasticsearch" elasticsearch 9200 9200
forward "mongo express" mongo-express 8082 8081
forward "mongodb"       mongodb       27017 27017
forward "tika"          tika          9998 9998
echo "  kafka broker     localhost:9092 (bootstrap.servers)"
kubectl -n "$NAMESPACE" port-forward svc/kafka 9092:9092 >/dev/null 2>&1 &
PIDS+=("$!")

wait
