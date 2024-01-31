{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "ska-dlm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ska-dlm.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ska-dlm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "ska-dlm.labels" }}
{{- if .Values.global.labels}}
app: {{ coalesce .Values.global.labels.app "ska-dlm.name" }}
{{- else }}
app: {{ include "ska-dlm.name" . }}
{{- end }}
chart: {{ include "ska-dlm.chart" . }}
release: {{ .Release.Name }}
heritage: {{ .Release.Service }}
system: {{ .Values.system }}
{{- end }}

{{/* Etcd host */}}
{{- define "ska-dlm.postgres-host" -}}
{{ include "ska-dlm.name" . }}-postgres-client.{{ .Release.Namespace }}
{{- end -}}

{{/* Init container to wait for configuration database availability */}}
{{- define "ska-dlm.wait-for-postgres" -}}
- name: wait-for-postgres
  image: {{ .Values.postgres.image }}:{{ .Values.postgres.version }}
  imagePullPolicy: {{ .Values.postgres.imagePullPolicy }}
  command: ["/bin/sh", "-c", "while ( ! etcdctl endpoint health ); do sleep 1; done"]
  env:
  - name: ETCDCTL_ENDPOINTS
    value: "http://{{ include "ska-dlm.postgres-host" . }}:2379"
  - name: ETCDCTL_API
    value: "3"
{{- end -}}