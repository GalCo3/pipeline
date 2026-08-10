# Helm Charts

One chart per component, grouped by role. Shared templates live in the
`hermes-common` library chart; every application chart depends on it instead of
repeating manifests.

```
helm-charts/
  services/                 the pipeline itself
    cargo/                  the service (Deployment, no listening port)
  utils/                    everything it runs against
    hermes-common/          library chart: Deployment / Job / CronJob /
                            Service / Secret / ConfigMap / PVC
    infra/                  backing stores, each with its UI alongside
      kafka/
        kafka/              Bitnami kafka 32.4.3, KRaft single node, PLAINTEXT
        kafka-ui/           Kafbat UI (topics, messages, consumer groups)
      elastic/
        elasticsearch/      Bitnami elasticsearch 22.1.6, single node, security off
        kibana/             Bitnami kibana 12.1.10, pointed at elasticsearch
      mongodb/
        mongodb/            Official mongo:8.0, standalone, database `hermes`
        mongo-express/      Mongo Express web UI
      minio/                Bitnami minio 17.0.21, standalone, bucket `cargo`
      tika/                 Apache Tika server for legacy/image formats
    observability/          where telemetry goes and what shows it
      otel-operator/        OpenTelemetry Operator: CRDs + sidecar injection
      otel-collector/       namespace collector + injected sidecar (CRs)
      mimir/                metrics backend (-target=all)
      loki/                 logs backend (-target=all)
      tempo/                traces backend (monolithic, OTLP ingest)
      grafana/              UI, with all three provisioned as datasources
    dev/                    local-only helpers, no production counterpart
      demo-producer/        suspended CronJob to trigger on demand, plus a
                            one-shot Job at install time
      es-index/             creates the cargo index + mappings (idempotent)
      headlamp/             Kubernetes dashboard: pods, live logs, exec terminal
  scripts/
    install.sh              build images, resolve deps, install everything
    port-forward.sh         expose every UI/API on localhost
  links.txt                 every local URL, plain text
```

In-cluster DNS names are pinned via `fullnameOverride`, so the addresses in
`services/cargo-lexical/values.yaml` hold regardless of release name: `kafka:9092`,
`minio:9000`, `elasticsearch:9200`, `tika:9998`.

## Local run (Docker Desktop Kubernetes)

Enable Kubernetes in Docker Desktop → Settings → Kubernetes, then:

```bash
./helm-charts/scripts/install.sh      # ~10 min on a cold cluster
./helm-charts/scripts/port-forward.sh # UI access, Ctrl-C to stop
```

Plain URL list: [links.txt](./links.txt).

| UI / API           | URL (while port-forward runs) | Credentials              |
| ------------------ | ----------------------------- | ------------------------ |
| Grafana            | http://localhost:3000         | anonymous, or admin / grafana |
| Kafka UI           | http://localhost:8080         | none                     |
| Kibana             | http://localhost:5601         | none                     |
| Headlamp           | http://localhost:8081         | none (see security note) |
| MinIO console      | http://localhost:9001         | minioadmin / minioadmin  |
| Elasticsearch API  | http://localhost:9200         | none                     |
| Mongo Express      | http://localhost:8082         | none                     |
| MongoDB            | localhost:27017               | root / mongoadmin        |
| Kafka bootstrap    | localhost:9092                | PLAINTEXT                |
| Mimir API          | http://localhost:8090         | none                     |
| Loki API           | http://localhost:3100         | none                     |
| Tempo API          | http://localhost:3200         | none                     |

Manual install, if you prefer step by step:

```bash
kubectl create namespace hermes
helm upgrade --install kafka          helm-charts/utils/infra/kafka/kafka           -n hermes --wait
helm upgrade --install minio          helm-charts/utils/infra/minio                 -n hermes --wait
helm upgrade --install elasticsearch  helm-charts/utils/infra/elastic/elasticsearch -n hermes --wait
helm upgrade --install tika           helm-charts/utils/infra/tika                  -n hermes --wait
helm upgrade --install mongodb        helm-charts/utils/infra/mongodb/mongodb       -n hermes --wait
helm upgrade --install kafka-ui       helm-charts/utils/infra/kafka/kafka-ui        -n hermes --wait
helm upgrade --install mongo-express  helm-charts/utils/infra/mongodb/mongo-express -n hermes --wait
helm upgrade --install kibana         helm-charts/utils/infra/elastic/kibana        -n hermes --wait
helm upgrade --install headlamp       helm-charts/utils/dev/headlamp                -n hermes --wait
helm upgrade --install mimir          helm-charts/utils/observability/mimir         -n hermes --wait
helm upgrade --install loki           helm-charts/utils/observability/loki          -n hermes --wait
helm upgrade --install tempo          helm-charts/utils/observability/tempo         -n hermes --wait
helm upgrade --install grafana        helm-charts/utils/observability/grafana       -n hermes --wait
helm upgrade --install otel-operator  helm-charts/utils/observability/otel-operator -n hermes --wait
helm upgrade --install otel-collector helm-charts/utils/observability/otel-collector -n hermes
helm upgrade --install es-index       helm-charts/utils/dev/es-index                -n hermes
helm upgrade --install cargo-lexical-lexical          helm-charts/services/cargo-lexical-lexical                    -n hermes
helm upgrade --install demo-producer  helm-charts/utils/dev/demo-producer           -n hermes
```

Check the result:

```bash
kubectl -n hermes logs -f deploy/cargo-lexical-lexical
kubectl -n hermes logs job/demo-producer
curl 'http://localhost:9200/cargo-files/_search?pretty'   # with port-forward running
```

Tear down:
`helm -n hermes uninstall cargo demo-producer tika kafka minio elasticsearch \
  mongodb kafka-ui kibana mongo-express headlamp es-index otel-collector otel-operator \
  mimir loki tempo grafana`

## Triggering the demo producer

`demo-producer` installs a **suspended CronJob** whose schedule never fires. It
exists to be run on demand:

- **Headlamp** → Workloads → Cron Jobs → `demo-producer` → the ⏵ / *Trigger*
  action spawns a Job from it immediately.
- **CLI equivalent:**
  `kubectl -n hermes create job manual-1 --from=cronjob/demo-producer`

Each run gets its own `RUN_SEED` (derived from the pod name), so every trigger
adds fresh documents instead of overwriting the previous batch. A one-shot Job
also runs at install/upgrade time; set `runOnInstall: false` to skip it.

What it produces comes from `demo-producer/examples/<service>.json`: ten example
messages per source, covering that source's legal payload shapes — the index,
update and delete routes, source aliases vs model field names, optional fields
present / absent / null, and for cargo every file type the extractor handles
plus the missing-object (dead letter) and unsupported-format (skipped) paths.
Records are produced **without a Kafka key**, like the real sources. `SOURCES`
picks which fixtures to produce (default: everything except `chief-lexical`,
whose indexing path calls the chief API); `TOPIC_<SOURCE>` overrides a fixture's
topic.

## Telemetry

```
                                                                    metrics --> mimir  :8080  --.
cargo (OTel SDK)  --OTLP--> otc-container      --OTLP--> hermes-collector --> logs --> loki :3100 --+--> grafana :3000
  localhost:4317            (injected sidecar)                             --> traces --> tempo :4317 -'
                                                                           --> prometheus :8889, debug/stdout
annotated pods    <--scrape-------------------------------- hermes-collector (prometheus receiver)
```

- The pod annotation `sidecar.opentelemetry.io/inject: "true"` (cargo
  `values.yaml`) makes the operator inject a collector sidecar, which is what
  listens on the `localhost:4317` the service exports to.
- The namespace collector (`hermes`) also scrapes any pod annotated
  `prometheus.io/scrape: "true"`, covering components that speak Prometheus
  rather than OTLP.
- `k8sattributes` tags every record with pod, namespace and deployment.
- Read the metrics:
  `kubectl -n hermes port-forward svc/hermes-collector 8889:8889` then
  `curl -s localhost:8889/metrics | grep cargo_`.
- The collector fans out to the three backends: `prometheusremotewrite` →
  Mimir, `otlphttp` → Loki's native OTLP endpoint (the `loki` exporter was
  removed from the collector), `otlp` → Tempo. Each is toggleable under
  `backends` in `utils/observability/otel-collector/values.yaml`.
- Grafana ships with all three provisioned as datasources and one dashboard
  (**Hermes / Hermes pipeline**); nothing has to be wired up in the UI.
- **Pointing at Grafana Cloud instead** means changing the `backends`
  endpoints and adding a `headers.authorization` to each exporter. The
  sidecars need no change; they only forward to the namespace collector.
- Tempo's metrics-generator remote-writes span metrics and service graphs into
  Mimir, which is what feeds Grafana's service map.

## Notes

- **Index mappings.** `utils/dev/es-index` creates `cargo-files-000001` with an
  explicit mapping for every `CargoEnrichedMessage` field and a write alias
  `cargo-files` (the name cargo indexes to). The job is idempotent — an
  existing index is left alone — so recreating the index means deleting it
  first, then `helm upgrade --install es-index ...`. The mapping is
  `dynamic: strict`: a field the mapping does not know about fails the write
  instead of silently guessing a type, so model drift surfaces immediately (in
  the DLS) rather than as a bad mapping.
- **Dead-letter store.** Messages the service cannot process go to MongoDB,
  `hermes.dls` — browse them in Mongo Express.
- **No OTLP collector.** `init_observability` exports to
  `localhost:4317`; with nothing listening, the pod logs a
  `StatusCode.UNAVAILABLE` warning every few seconds. Harmless, noisy — add a
  collector or point `OTEL_EXPORTER_OTLP_ENDPOINT` at one to silence it.
- **Host access is via port-forward.** Docker Desktop's Kubernetes node is not
  on the host network, so NodePort addresses and `LoadBalancer` external IPs do
  not resolve from macOS. The NodePort values in the infra charts are kept for
  clusters where they do work; `scripts/port-forward.sh` is the reliable path.
- **MongoDB uses the official image**, not a Bitnami wrapper: the
  `bitnamilegacy` MongoDB tags are amd64-only and will not run on Apple
  Silicon. The chart is built on `hermes-common` with a PVC template.
- **Bitnami images.** Bitnami withdrew its public Docker Hub catalog; the usable
  tags now live under `bitnamilegacy/*`. Each wrapper chart pins those
  repositories and sets `global.security.allowInsecureImages: true`, which the
  Bitnami charts require before accepting a non-default image.
- **Single-node Kafka.** `overrideConfiguration` forces replication factor 1.
  Without it `__consumer_offsets` is never created on a one-node cluster and
  consumers hang forever without joining their group.
- **Local images.** `cargo` and `demo-producer` use `pullPolicy: IfNotPresent`
  with a `:local` tag, resolved from the Docker Desktop image store.
- **OpenShift compatibility.** The application charts pin no UID: pods request
  `runAsNonRoot` + `RuntimeDefault` seccomp and drop all capabilities, so the
  `restricted-v2` SCC can assign an arbitrary UID. The images are group-0 owned
  and group-writable to match. `kafka-ui` is the exception — its image declares
  a named user, so UID 100 is set explicitly. The Bitnami infra charts are
  dev-only: on a real OpenShift cluster those come from platform operators
  (AMQ Streams, ODF/S3, Elasticsearch), and
  `elasticsearch.sysctlImage.enabled` must be turned off there, since node
  sysctls are set by a MachineConfig.
- **Security, local only.** Credentials sit in plaintext `secretEnv` values, and
  Headlamp runs with `cluster-admin` plus `unsafeUseServiceAccountToken: true`,
  which signs every visitor in as that admin service account. Both are fine on a
  single-user laptop cluster and unacceptable anywhere shared — point the charts
  at existing Secrets and real per-user auth before promoting them.
