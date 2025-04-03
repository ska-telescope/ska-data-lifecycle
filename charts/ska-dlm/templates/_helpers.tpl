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
see https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
*/}}
{{- define "ska-dlm.labels" }}
{{- if .Values.global.labels}}
app.kubernetes.io/name: {{ coalesce .Values.global.labels.app "ska-dlm.name" }}
{{- else }}
app.kubernetes.io/name: {{ include "ska-dlm.name" . }}
{{- end }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ include "ska-dlm.chart" . }}
system: {{ .Values.system }}
{{- end }}

{{/*
Postgrest labels
*/}}
{{- define "ska-dlm.postgrest.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.postgrest.component }}
subsystem: {{ .Values.postgrest.subsystem }}
intent: production
{{- end }}

{{/* PostgreSQL service name */}}
{{- define "ska-dlm.postgresql.name" }}
{{- printf "%s-%s" .Release.Name .Values.postgresql.nameOverride -}}
{{- end}}

{{/*
Generates the PostgreREST Secret name
*/}}
{{- define "ska-dlm.postgrest.db-auth-secret-name" -}}
{{- if not .Values.postgrest.db_auth_secret.create -}}
{{- if not .Values.postgrest.db_auth_secret.name -}}
{{- fail "postgrest.db_auth_secret.enable=false but no postgrest.secret.name given" }}
{{- else -}}
{{ .Values.postgrest.db_auth_secret.name }}
{{- end -}}
{{- else -}}
{{- printf "%s-postgrest-secret" (include "ska-dlm.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Migration labels
*/}}
{{- define "ska-dlm.migration.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.migration.component }}
subsystem: {{ .Values.migration.subsystem }}
intent: production
{{- end }}

{{/*
Ingest labels
*/}}
{{- define "ska-dlm.ingest.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.ingest.component }}
subsystem: {{ .Values.ingest.subsystem }}
intent: production
{{- end }}

{{/*
Storage labels
*/}}
{{- define "ska-dlm.storage.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.storage.component }}
subsystem: {{ .Values.storage.subsystem }}
intent: production
{{- end }}

{{/*
Request labels
*/}}
{{- define "ska-dlm.request.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.request.component }}
subsystem: {{ .Values.request.subsystem }}
intent: production
{{- end }}

{{/*
RClone labels
*/}}
{{- define "ska-dlm.rclone.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.rclone.component }}
subsystem: {{ .Values.rclone.subsystem }}
intent: production
{{- end }}

{{/*
Gateway labels
*/}}
{{- define "ska-dlm.gateway.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.gateway.component }}
subsystem: {{ .Values.gateway.subsystem }}
intent: production
{{- end }}

{{/*
Keycloak labels
*/}}
{{- define "ska-dlm.keycloak.labels" }}
{{- include "ska-dlm.labels" . }}
component: {{ .Values.keycloak.component }}
subsystem: {{ .Values.keycloak.subsystem }}
intent: production
{{- end }}


{{/*
Rclone secret name
*/}}
{{- define "ska-dlm.rclone.secret.name" -}}
{{- printf "%s%s" .Values.rclone.secret.name (ternary "-vso" "" .Values.rclone.secret.vault.enabled) -}}
{{- end -}}