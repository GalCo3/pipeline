{{/*
PersistentVolumeClaim for single-replica stateful components.
Usage: {{ include "hermes-common.pvc" . }}
*/}}
{{- define "hermes-common.pvc" -}}
{{- if and .Values.persistence .Values.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "hermes-common.fullname" . }}
  labels:
    {{- include "hermes-common.labels" . | nindent 4 }}
spec:
  accessModes:
    - {{ .Values.persistence.accessMode | default "ReadWriteOnce" }}
  resources:
    requests:
      storage: {{ .Values.persistence.size | default "1Gi" }}
  {{- with .Values.persistence.storageClass }}
  storageClassName: {{ . }}
  {{- end }}
{{- end }}
{{- end }}
