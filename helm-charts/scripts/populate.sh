#!/usr/bin/env bash
# Opposite of clean.sh: re-populates the pipeline with data. Recreates the
# Elasticsearch index and alias (es-index job) and re-runs the demo producer,
# which uploads sample documents to MinIO and produces their Kafka messages —
# the topic is auto-created on first produce. Infrastructure must already be
# installed (scripts/install.sh).
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
CHARTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Ensuring consumer is running"
kubectl -n "$NAMESPACE" scale deploy/cargo-lexical --replicas=1 2>/dev/null || true

# Completed jobs are immutable and helm skips unchanged manifests, so delete
# the old job first — the upgrade then recreates and re-runs it.
rerun_job() {
    local release="$1" chart="$2"

    echo "==> Re-running $release"
    kubectl -n "$NAMESPACE" delete job "$release" --ignore-not-found >/dev/null
    helm upgrade --install "$release" "$CHARTS_DIR/$chart" \
        -n "$NAMESPACE" --reuse-values >/dev/null
    kubectl -n "$NAMESPACE" wait --for=condition=complete "job/$release" --timeout=300s
}

rerun_job es-index      utils/dev/es-index
rerun_job demo-producer utils/dev/demo-producer

echo "Done. Documents indexed; DLQ test message (id ending 99) in the dead letter store."
