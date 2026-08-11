{{/*
ConfigMap built from the `configFiles` map: each key becomes a file, each value
is rendered as JSON (objects/lists) or used verbatim (strings).
Usage: {{ include "hermes-common.configmap" . }}
*/}}
{{- define "hermes-common.configmap" -}}
{{- if .Values.configFiles }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
data:
  {{- range $name, $content := .Values.configFiles }}
  {{ $name }}: |
    {{- if kindIs "string" $content }}
    {{- $content | nindent 4 }}
    {{- else }}
    {{- $content | toPrettyJson | nindent 4 }}
    {{- end }}
  {{- end }}
{{- end }}
{{- end }}
