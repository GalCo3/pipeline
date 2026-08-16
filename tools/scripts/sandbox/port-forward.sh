#!/usr/bin/env bash
# Forwards every UI and API to localhost. Ctrl-C stops all of them.
#
# Docker Desktop's Kubernetes node is not reachable on the host network, so
# NodePort/LoadBalancer addresses do not resolve — port-forward is the way in.
#
# Docker Desktop does bind some of these ports itself: it publishes every
# NodePort Service on localhost at the Service's own port (8080 kafka-ui,
# 5601 kibana, 9200 elasticsearch, 27017 mongodb, 8081 mongo-express, …). Those
# binds exist before this script runs and they are not always routing — a
# Desktop restart is what repairs that. Rather than skip those services, each
# one falls back to the same port + 10000 (9200 -> 19200) and prints where it
# actually landed. FALLBACK_OFFSET overrides the 10000.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
FALLBACK_OFFSET="${FALLBACK_OFFSET:-10000}"
PIDS=()

port_taken() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

# SUFFIX turns the printed address from an http:// URL into "localhost:<port>
# <suffix>", for the things that are not web UIs (Kafka, MongoDB).
forward() {
    local name="$1" svc="$2" local_port="$3" remote_port="$4" suffix="${5:-}"
    local port="$local_port" note=""

    # kubectl exits immediately when the local port is taken, and its error goes
    # to /dev/null with everything else — so check first and move aside instead.
    if port_taken "$port"; then
        port=$((local_port + FALLBACK_OFFSET))
        note=" (${local_port} taken)"
        if port_taken "$port"; then
            printf '  %-16s SKIPPED — localhost:%s and localhost:%s are both in use\n' \
                "$name" "$local_port" "$port"
            return
        fi
    fi

    kubectl -n "$NAMESPACE" port-forward "svc/$svc" "$port:$remote_port" >/dev/null 2>&1 &
    PIDS+=("$!")

    local address="http://localhost:$port"
    [[ -n "$suffix" ]] && address="localhost:$port $suffix"
    printf '  %-16s %s%s\n' "$name" "$address" "$note"
}

cleanup() {
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

echo "Forwarding (Ctrl-C to stop)"
echo
echo "UIs:"
forward "grafana"       grafana       3000 3000
forward "kafka-ui"      kafka-ui      8080 8080
forward "kibana"        kibana        5601 5601
# Not 8081: that is mongo-express's Service port, so Docker Desktop holds it and
# headlamp would spend its life on the fallback.
forward "headlamp"      headlamp      8084 80
forward "minio console" minio-console 9001 9090
forward "mongo express" mongo-express 8082 8081
# 8083 is not free-choice: tokens carry iss=http://localhost:8083/realms/... from
# the chart's KC_HOSTNAME, and the backend validates iss. If this one ever lands
# on the fallback, fix the collision rather than using the fallback URL — the
# login will fail against an issuer the token does not match.
forward "keycloak"      keycloak      8083 8080
# Same constraint as keycloak, from the other side: next-auth posts back to
# a fixed callback path (/api/auth/callback/keycloak) under the origin in
# AUTH_URL, so the console chart's AUTH_URL, this port, and the realm's
# redirectUris all have to agree on 8086. On the fallback port the login fails
# with `invalid_redirect_uri`, so fix the collision rather than using it.
forward "dls-console"    dls-console          8086 8080

echo
echo "Backends:"
forward "mimir"         mimir         8090 8080
forward "loki"          loki          3100 3100
forward "tempo"         tempo         3200 3200
forward "minio s3"      minio         9000 9000
forward "elasticsearch" elasticsearch 9200 9200
forward "mongodb"       mongodb       27017 27017 "(root / mongoadmin)"
forward "tika"          tika          9998 9998
# Both Triton ports: a client is configured for one protocol or the other, and
# either should be reachable from the host.
forward "triton http"   triton        8000 8000
forward "triton grpc"   triton        8001 8001 "(grpc)"
forward "kafka broker"  kafka         9092 9092 "(bootstrap.servers)"
echo

wait
