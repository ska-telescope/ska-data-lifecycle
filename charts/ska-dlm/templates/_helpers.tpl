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

{{/*
Postgrest labels
*/}}
{{- define "ska-dlm.postgrest.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.postgrest.component }}
subsystem: {{ .Values.postgrest.subsystem }}
function: {{ .Values.postgrest.function }}
domain: {{ .Values.postgrest.domain }}
intent: production
{{- end }}

{{/* PostgreSQL service name */}}
{{- define "ska-dlm.postgresql.name" }}
{{- printf "%s-%s" .Release.Name .Values.postgresql.nameOverride -}}
{{- end}}

{{/*
Template to generate the Postgresql URI
*/}}
{{- define "ska-dlm.postgrest.postgresql.uri" -}}
{{- if .Values.postgrest.db_uri }}
{{ .Values.postgrest.db_uri }}
{{- else }}
{{- $user := .Values.postgresql.auth.username -}}
{{- $pass := .Values.postgresql.auth.password -}}
{{- $host := include "ska-dlm.postgresql.name" . -}}
{{- $db := .Values.postgresql.auth.database -}}
{{- printf "postgres://%s:%s@%s/%s" $user $pass $host $db -}}
{{- end -}}
{{- end -}}