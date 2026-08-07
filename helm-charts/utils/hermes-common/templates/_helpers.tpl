{{/*
Chart name, overridable with .Values.nameOverride
*/}}
{{- define "hermes-common.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name. .Values.fullnameOverride wins, which is how the
charts keep predictable in-cluster DNS names (cargo, tika, demo-producer).
*/}}
{{- define "hermes-common.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "hermes-common.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "hermes-common.labels" -}}
helm.sh/chart: {{ include "hermes-common.chart" . }}
{{ include "hermes-common.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: hermes-pipeline
{{- end }}

{{- define "hermes-common.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hermes-common.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "hermes-common.image" -}}
{{- $registry := .Values.image.registry | default "" -}}
{{- $repo := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion | default "latest" -}}
{{- if $registry }}{{ printf "%s/%s:%s" $registry $repo $tag }}{{ else }}{{ printf "%s:%s" $repo $tag }}{{ end }}
{{- end }}

{{/*
Env vars from the `env` map (plain values) plus `extraEnv` (raw list).
*/}}
{{- define "hermes-common.env" -}}
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- with .Values.extraEnv }}
{{- toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod security context. OpenShift-friendly: no UID pinning, so the restricted-v2
SCC can assign an arbitrary UID from the namespace range.
*/}}
{{- define "hermes-common.podSecurityContext" -}}
{{- if .Values.podSecurityContext }}
{{- toYaml .Values.podSecurityContext }}
{{- else }}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}
{{- end }}

{{- define "hermes-common.containerSecurityContext" -}}
{{- if .Values.containerSecurityContext }}
{{- toYaml .Values.containerSecurityContext }}
{{- else }}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: false
capabilities:
  drop:
    - ALL
{{- end }}
{{- end }}

{{/*
Shared pod spec body. Used by both the deployment and the job templates.
*/}}
{{- define "hermes-common.podSpec" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
securityContext:
  {{- include "hermes-common.podSecurityContext" . | nindent 2 }}
containers:
  - name: {{ .Chart.Name }}
    image: {{ include "hermes-common.image" . }}
    imagePullPolicy: {{ .Values.image.pullPolicy | default "IfNotPresent" }}
    securityContext:
      {{- include "hermes-common.containerSecurityContext" . | nindent 6 }}
    {{- with .Values.command }}
    command: {{ toYaml . | nindent 6 }}
    {{- end }}
    {{- with .Values.args }}
    args: {{ toYaml . | nindent 6 }}
    {{- end }}
    {{- $envBlock := include "hermes-common.env" . }}
    {{- if trim $envBlock }}
    env:
      {{- $envBlock | nindent 6 }}
    {{- end }}
    {{- if or .Values.secretEnv .Values.envFrom }}
    envFrom:
      {{- if .Values.secretEnv }}
      - secretRef:
          name: {{ include "hermes-common.fullname" . }}
      {{- end }}
      {{- with .Values.envFrom }}
      {{- toYaml . | nindent 6 }}
      {{- end }}
    {{- end }}
    {{- if or .Values.service.enabled .Values.extraContainerPorts }}
    ports:
      {{- if .Values.service.enabled }}
      - name: {{ .Values.service.portName | default "http" }}
        containerPort: {{ .Values.service.targetPort | default .Values.service.port }}
        protocol: TCP
      {{- end }}
      {{- with .Values.extraContainerPorts }}
      {{- toYaml . | nindent 6 }}
      {{- end }}
    {{- end }}
    {{- with .Values.livenessProbe }}
    livenessProbe: {{ toYaml . | nindent 6 }}
    {{- end }}
    {{- with .Values.readinessProbe }}
    readinessProbe: {{ toYaml . | nindent 6 }}
    {{- end }}
    {{- with .Values.resources }}
    resources: {{ toYaml . | nindent 6 }}
    {{- end }}
    {{- with .Values.volumeMounts }}
    volumeMounts: {{ toYaml . | nindent 6 }}
    {{- end }}
{{- with .Values.volumes }}
volumes: {{ toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.nodeSelector }}
nodeSelector: {{ toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations: {{ toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity: {{ toYaml . | nindent 2 }}
{{- end }}
{{- end }}
