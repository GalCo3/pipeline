#!/usr/bin/env bash
# Opposite of clean.sh: re-populates the pipeline with data. Recreates the
# Elasticsearch index and alias (es-index job) and re-runs the demo producer,
# which uploads the cargo sample documents to MinIO and produces ten example
# messages per source — topics are auto-created on first produce.
# Infrastructure must already be installed (tools/scripts/install.sh). This reuses the
# already-built demo-producer image: after editing produce.py or its example
# fixtures, re-run tools/scripts/install.sh so a fresh image tag is built.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHARTS_DIR="$REPO_ROOT/helm-charts"

SERVICES=(candy-reports-lexical cargo-lexical chat-lexical chat-rooms-lexical chat-users-lexical chief-lexical)

# The consumers come up last, after the jobs, for two reasons: their memory
# requests fill the single dev node, leaving nothing for the job pods to
# schedule into, and a consumer subscribed to a topic that does not exist yet
# dies on UNKNOWN_TOPIC_OR_PART — the topics are auto-created by the producer.
# Every service reads with auto.offset.reset=earliest, so starting after the
# produce still consumes the whole backlog.
echo "==> Scaling consumers down while the jobs run"
for service in "${SERVICES[@]}"; do
    kubectl -n "$NAMESPACE" scale "deploy/$service" --replicas=0 2>/dev/null || true
done
# Scale returns as soon as the spec is written; the pods still hold their memory
# requests until they are gone, which is what the job pods are waiting for.
kubectl -n "$NAMESPACE" wait --for=delete pod \
    -l "app.kubernetes.io/instance in ($(IFS=,; echo "${SERVICES[*]}"))" \
    --timeout=120s >/dev/null 2>&1 || true

# Completed jobs are immutable and helm skips unchanged manifests, so delete
# the old job first — the upgrade then recreates and re-runs it.
rerun_job() {
    local release="$1" chart="$2"

    echo "==> Re-running $release"
    kubectl -n "$NAMESPACE" delete job "$release" --ignore-not-found >/dev/null
    # --reset-then-reuse-values, not --reuse-values: the latter pins every value
    # to the last release, so an edited values.yaml (a new source, a new index)
    # would be silently ignored. This takes the chart's values and re-applies
    # only what install.sh passed with --set, which is the image tag.
    helm upgrade --install "$release" "$CHARTS_DIR/$chart" \
        -n "$NAMESPACE" --reset-then-reuse-values >/dev/null
    kubectl -n "$NAMESPACE" wait --for=condition=complete "job/$release" --timeout=300s
}

rerun_job es-index      local-infra/backing/elastic/es-index
rerun_job demo-producer local-infra/tooling/demo-producer

echo "==> Starting consumers"
for service in "${SERVICES[@]}"; do
    kubectl -n "$NAMESPACE" scale "deploy/$service" --replicas=1 2>/dev/null || true
done

echo "Done. Ten example messages per source produced (see tools/demo-producer/examples);"
echo "the cargo missing-object example lands in the dead letter store by design."
