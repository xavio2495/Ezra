{{/* Chart name */}}
{{- define "ezra.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully-qualified app name */}}
{{- define "ezra.fullname" -}}
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

{{- define "ezra.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ezra.labels" -}}
helm.sh/chart: {{ include "ezra.chart" . }}
{{ include "ezra.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "ezra.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ezra.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "ezra.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ezra.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "ezra.secretName" -}}
{{- if eq .Values.secrets.backend "existing" -}}
{{- required "secrets.existingSecret is required when secrets.backend=existing" .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "ezra.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "ezra.redisUrl" -}}
{{- if .Values.redis.enabled -}}
redis://{{ include "ezra.fullname" . }}-redis:6379
{{- else -}}
{{- required "redis.url is required when redis.enabled=false" .Values.redis.url -}}
{{- end -}}
{{- end -}}

{{- define "ezra.qdrantUrl" -}}
{{- if .Values.qdrant.enabled -}}
http://{{ include "ezra.fullname" . }}-qdrant:6333
{{- else -}}
{{- required "qdrant.url is required when qdrant.enabled=false" .Values.qdrant.url -}}
{{- end -}}
{{- end -}}
