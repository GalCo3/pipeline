{{/*
Secret built from the `secretEnv` map. Consumed automatically as envFrom by
the shared pod spec, so charts only need to list the keys in values.yaml.
Usage: {{ include "hermes-common.secret" . }}
*/}}
{{- define "hermes-common.secret" -}}
{{- if .Values.secretEnv }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
type: Opaque
stringData:
  {{- range $key, $value := .Values.secretEnv }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
{{- end }}
