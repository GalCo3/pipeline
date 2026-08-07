# Agent Guide — Helm Charts

Local Kubernetes stack (Docker Desktop) standing in for the OpenShift target.
Full usage, URLs and caveats: [README.md](./README.md).

## Layout

- `services/` — **this repo's own services, and nothing else.** Today that is
  `cargo`. A service from the monorepo's `services/` gets a chart here;
  anything it merely runs against does not.
- `utils/` — everything the services depend on, in four buckets:
  - `hermes-common/` — the library chart every application chart depends on.
  - `infra/` — backing stores, each with its UI in the same stack folder:
    `kafka/` (kafka + kafka-ui), `elastic/` (elasticsearch + kibana),
    `mongodb/` (mongodb + mongo-express), plus `minio/` and `tika/`.
  - `observability/` — `otel-operator`, `otel-collector`, and the Grafana
    stack (`mimir`, `loki`, `tempo`, `grafana`).
  - `dev/` — local-only, no production counterpart: `demo-producer`,
    `es-index`, `headlamp`.
- `scripts/` — `install.sh` (build + install everything), `port-forward.sh` (UIs).
- `links.txt` — every local URL, plain text.

Moving a chart means fixing three things: the depth-relative `file://` path to
`hermes-common` in its `Chart.yaml`, the paths in both scripts, and the
vendored `charts/*.tgz` (`helm dependency update` rebuilds those).

## Conventions

- **Reuse the library chart.** Application charts carry no manifests of their
  own: `templates/*.yaml` is a one-line `{{ include "hermes-common.<kind>" . }}`
  and everything is expressed in `values.yaml`. Add a new `define` to
  `utils/hermes-common/templates/` rather than hand-writing a manifest in a
  component chart.
- **Values contract** consumed by the library: `image.{registry,repository,tag,pullPolicy}`,
  `replicaCount`, `env` (map), `secretEnv` (map → Secret + envFrom), `envFrom`,
  `service.{enabled,type,port,targetPort,portName,nodePort}`, probes, `resources`,
  `command`/`args`, `volumes`/`volumeMounts`, `persistence.{enabled,size,accessMode,storageClass}`,
  `configFiles` (map → ConfigMap, and a `checksum/config` pod annotation),
  `service.extraPorts`/`extraContainerPorts`, `strategy`,
  `podSecurityContext`, `containerSecurityContext`, plus
  `restartPolicy`/`backoffLimit`/`ttlSecondsAfterFinished` for Jobs and
  `cronJob.{schedule,suspend,concurrencyPolicy,...}` for CronJobs.
- **On-demand work is a suspended CronJob**, not a bare Job — that is what
  gives Headlamp (and `kubectl create job --from=cronjob/...`) something to
  trigger. See `utils/dev/demo-producer`.
- **Third-party charts get a wrapper chart**, never a raw `helm install`: a
  `Chart.yaml` dependency plus a `values.yaml` with everything pinned. Bitnami
  images must come from `bitnamilegacy/*` with
  `global.security.allowInsecureImages: true` — and check the tag actually has
  an arm64 manifest, since many legacy tags are amd64-only (this is why
  `mongodb` runs the official image on the library chart instead).
- **Stay OpenShift-safe.** No UID pinning, no privileged containers, no hostPath;
  drop all capabilities and keep `runAsNonRoot`. If an image forces a UID (as
  `kafka-ui` does), say why in a comment next to the override.
- **Fixed DNS names.** Every chart sets `fullnameOverride`, because
  `services/cargo-lexical/values.yaml` addresses dependencies by plain service name.
- **A ReadWriteOnce volume implies `strategy.type: Recreate`.** A rolling
  update deadlocks: the new pod waits for a claim the old pod still holds.
  Kubernetes rejects switching an existing Deployment to `Recreate` while
  `spec.strategy.rollingUpdate` is set, so patch it out first:
  `kubectl -n hermes patch deploy <name> -p '{"spec":{"strategy":{"rollingUpdate":null,"type":"Recreate"}}}'`
- **Config lives in `configFiles`, mounted with `subPath`.** subPath mounts
  never see ConfigMap updates, which is why the library stamps a
  `checksum/config` annotation to roll the pod on change.
- **Images are tagged per build** (`install.sh` generates `dev-<timestamp>`);
  reusing a fixed tag leaves the previously cached image running.
