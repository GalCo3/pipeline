{{/*
Deployment for long-running components (cargo, tika).
Usage: {{ include "hermes-common.deployment" . }}
*/}}
{{- define "hermes-common.deployment" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount | default 1 }}
  {{- with .Values.strategy }}
  # ReadWriteOnce volumes need Recreate: a rolling update would deadlock with
  # the new pod waiting for a claim the old pod still holds.
  strategy: {{ toYaml . | nindent 4 }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "hermes-common.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "hermes-common.selectorLabels" . | nindent 8 }}
      {{- if or .Values.podAnnotations .Values.configFiles }}
      annotations:
        {{- with .Values.podAnnotations }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
        {{- if .Values.configFiles }}
        # subPath mounts never see ConfigMap updates, so a config change has to
        # roll the pod.
        checksum/config: {{ .Values.configFiles | toYaml | sha256sum }}
        {{- end }}
      {{- end }}
    spec:
      {{- include "hermes-common.podSpec" . | nindent 6 }}
{{- end }}

{{/*
Job for run-to-completion components (demo-producer).
Usage: {{ include "hermes-common.job" . }}
*/}}
{{- define "hermes-common.job" -}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
  annotations:
    # Re-running `helm upgrade` should re-run the job, so it is replaced on upgrade.
    helm.sh/hook: post-install,post-upgrade
    helm.sh/hook-weight: "5"
    helm.sh/hook-delete-policy: before-hook-creation
spec:
  backoffLimit: {{ .Values.backoffLimit | default 6 }}
  {{- with .Values.ttlSecondsAfterFinished }}
  ttlSecondsAfterFinished: {{ . }}
  {{- end }}
  template:
    metadata:
      labels:
        {{- include "hermes-common.selectorLabels" . | nindent 8 }}
      {{- with .Values.podAnnotations }}
      annotations: {{ toYaml . | nindent 8 }}
      {{- end }}
    spec:
      restartPolicy: {{ .Values.restartPolicy | default "OnFailure" }}
      {{- include "hermes-common.podSpec" . | nindent 6 }}
{{- end }}

{{/*
CronJob for on-demand work. With `cronJob.suspend: true` and a schedule that
never fires, it exists purely as a template to trigger runs from — the Trigger
button in Headlamp, or `kubectl create job --from=cronjob/<name>`.
Usage: {{ include "hermes-common.cronjob" . }}
*/}}
{{- define "hermes-common.cronjob" -}}
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
spec:
  schedule: {{ .Values.cronJob.schedule | quote }}
  suspend: {{ .Values.cronJob.suspend }}
  concurrencyPolicy: {{ .Values.cronJob.concurrencyPolicy | default "Forbid" }}
  successfulJobsHistoryLimit: {{ .Values.cronJob.successfulJobsHistoryLimit | default 3 }}
  failedJobsHistoryLimit: {{ .Values.cronJob.failedJobsHistoryLimit | default 1 }}
  jobTemplate:
    metadata:
      labels:
        {{- include "hermes-common.selectorLabels" . | nindent 8 }}
    spec:
      backoffLimit: {{ .Values.backoffLimit | default 6 }}
      {{- with .Values.ttlSecondsAfterFinished }}
      ttlSecondsAfterFinished: {{ . }}
      {{- end }}
      template:
        metadata:
          labels:
            {{- include "hermes-common.selectorLabels" . | nindent 12 }}
          {{- with .Values.podAnnotations }}
          annotations: {{ toYaml . | nindent 12 }}
          {{- end }}
        spec:
          restartPolicy: {{ .Values.restartPolicy | default "OnFailure" }}
          {{- include "hermes-common.podSpec" . | nindent 10 }}
{{- end }}

{{/*
Service, rendered only when .Values.service.enabled is true.
Usage: {{ include "hermes-common.service" . }}
*/}}
{{- define "hermes-common.service" -}}
{{- if .Values.service.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type | default "ClusterIP" }}
  ports:
    - name: {{ .Values.service.portName | default "http" }}
      port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort | default .Values.service.port }}
      protocol: TCP
      {{- if and (eq (.Values.service.type | default "ClusterIP") "NodePort") .Values.service.nodePort }}
      nodePort: {{ .Values.service.nodePort }}
      {{- end }}
    {{- with .Values.service.extraPorts }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
  selector:
    {{- include "hermes-common.selectorLabels" . | nindent 4 }}
{{- end }}
{{- end }}
