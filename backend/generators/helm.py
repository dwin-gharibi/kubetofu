import logging
from typing import Any, Dict, List, Tuple

import yaml

from generators.base import (
    BaseGenerator,
    ErrorCategory,
    GenerationContext,
    GenerationResult,
    IaCType,
    ValidationError,
)

logger = logging.getLogger(__name__)


class HelmChartGenerator(BaseGenerator):
    iac_type = IaCType.HELM

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_chart_structure,
            self._validate_values,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()

        chart_name = self._extract_chart_name(context)
        config = self._parse_chart_config(context)

        files = {}

        files["Chart.yaml"] = self._generate_chart_yaml(chart_name, context)
        files["values.yaml"] = self._generate_values_yaml(config, context)
        files["templates/_helpers.tpl"] = self._generate_helpers(chart_name)
        files["templates/deployment.yaml"] = self._generate_deployment_template(config)
        files["templates/service.yaml"] = self._generate_service_template(config)
        files["templates/ingress.yaml"] = self._generate_ingress_template(config)
        files["templates/configmap.yaml"] = self._generate_configmap_template(config)
        files["templates/secret.yaml"] = self._generate_secret_template(config)
        files["templates/hpa.yaml"] = self._generate_hpa_template(config)
        files["templates/serviceaccount.yaml"] = self._generate_serviceaccount_template(
            config
        )
        files["templates/NOTES.txt"] = self._generate_notes(chart_name)

        if config.get("persistence", {}).get("enabled"):
            files["templates/pvc.yaml"] = self._generate_pvc_template(config)

        if config.get("networkPolicy", {}).get("enabled"):
            files["templates/networkpolicy.yaml"] = (
                self._generate_networkpolicy_template(config)
            )

        code = self._combine_files(files)

        result = GenerationResult.create(
            iac_type=self.iac_type,
            code=code,
            generation_time=time.time() - start_time,
        )
        result.files = files

        return result

    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "--- # Chart.yaml" in code or "---\n# Chart.yaml" in code:
            pass
        else:
            try:
                yaml.safe_load(code)
            except yaml.YAMLError as e:
                errors.append(
                    ValidationError(
                        category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                        message=f"Invalid YAML syntax: {e}",
                    )
                )
                return False, errors

        return True, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        required_patterns = [
            ("{{ .Chart.Name }}", "Chart.Name reference"),
            ("{{ .Release.Name }}", "Release.Name reference"),
            ("{{ .Values.", "Values reference"),
        ]

        for pattern, name in required_patterns:
            if pattern not in code and pattern.replace("{{ ", "{{") not in code:
                pass

        if "{{-" in code and "-}}" not in code:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                    message="Unbalanced whitespace control in templates",
                    severity="warning",
                )
            )

        return True, errors

    def _validate_chart_structure(
        self, code: str
    ) -> Tuple[bool, List[ValidationError]]:
        errors = []

        required_files = ["Chart.yaml", "values.yaml"]
        for filename in required_files:
            if filename not in code:
                errors.append(
                    ValidationError(
                        category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                        message=f"Missing required file: {filename}",
                    )
                )

        return len(errors) == 0, errors

    def _validate_values(self, code: str) -> Tuple[bool, List[ValidationError]]:
        return True, []

    def _extract_chart_name(self, context: GenerationContext) -> str:
        request = context.natural_language_request.lower()

        for word in request.split():
            if word.isalnum() and len(word) > 2:
                return word.replace(" ", "-")

        return "app"

    def _parse_chart_config(self, context: GenerationContext) -> Dict[str, Any]:
        config = {
            "replicaCount": 3 if "production" in context.environment else 1,
            "image": {
                "repository": "nginx",
                "tag": "latest",
                "pullPolicy": "IfNotPresent",
            },
            "service": {
                "type": "ClusterIP",
                "port": 80,
            },
            "ingress": {
                "enabled": False,
                "className": "",
                "hosts": [],
                "tls": [],
            },
            "resources": {
                "limits": {"cpu": "500m", "memory": "512Mi"},
                "requests": {"cpu": "100m", "memory": "128Mi"},
            },
            "autoscaling": {
                "enabled": False,
                "minReplicas": 1,
                "maxReplicas": 10,
                "targetCPUUtilizationPercentage": 80,
            },
            "persistence": {
                "enabled": False,
                "storageClass": "",
                "size": "8Gi",
            },
            "networkPolicy": {
                "enabled": False,
            },
            "serviceAccount": {
                "create": True,
                "automount": True,
                "name": "",
            },
        }

        request = context.natural_language_request.lower()

        if "autoscal" in request or "hpa" in request:
            config["autoscaling"]["enabled"] = True

        if "ingress" in request or "domain" in request:
            config["ingress"]["enabled"] = True

        if "persistent" in request or "storage" in request or "volume" in request:
            config["persistence"]["enabled"] = True

        if "network policy" in request or "networkpolicy" in request:
            config["networkPolicy"]["enabled"] = True

        return config

    def _generate_chart_yaml(self, chart_name: str, context: GenerationContext) -> str:
        chart = {
            "apiVersion": "v2",
            "name": chart_name,
            "description": f"A Helm chart for {context.natural_language_request[:50]}",
            "type": "application",
            "version": "0.1.0",
            "appVersion": "1.0.0",
            "keywords": ["kubetofu", "auto-generated"],
            "home": "",
            "sources": [],
            "maintainers": [{"name": "Kube-Tofu", "email": "kubetofu@example.com"}],
        }

        return yaml.dump(chart, default_flow_style=False, sort_keys=False)

    def _generate_values_yaml(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        header = f"""# Default values for {self._extract_chart_name(context)}
# Auto-generated by Kube-Tofu
# This is a YAML-formatted file.
# Declare variables to be passed into your templates.

"""
        return header + yaml.dump(config, default_flow_style=False, sort_keys=False)

    def _generate_helpers(self, chart_name: str) -> str:
        return f'''{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{chart_name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
*/}}}}
{{{{- define "{chart_name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Create chart name and version as used by the chart label.
*/}}}}
{{{{- define "{chart_name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{chart_name}.labels" -}}}}
helm.sh/chart: {{{{ include "{chart_name}.chart" . }}}}
{{{{ include "{chart_name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{chart_name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{chart_name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}

{{{{/*
Create the name of the service account to use
*/}}}}
{{{{- define "{chart_name}.serviceAccountName" -}}}}
{{{{- if .Values.serviceAccount.create }}}}
{{{{- default (include "{chart_name}.fullname" .) .Values.serviceAccount.name }}}}
{{{{- else }}}}
{{{{- default "default" .Values.serviceAccount.name }}}}
{{{{- end }}}}
{{{{- end }}}}
'''

    def _generate_deployment_template(self, config: Dict[str, Any]) -> str:
        return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        {{- include "app.labels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "app.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- if .Values.persistence.enabled }}
          volumeMounts:
            - name: data
              mountPath: /data
          {{- end }}
          envFrom:
            - configMapRef:
                name: {{ include "app.fullname" . }}
            - secretRef:
                name: {{ include "app.fullname" . }}
                optional: true
      {{- if .Values.persistence.enabled }}
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: {{ include "app.fullname" . }}
      {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
"""

    def _generate_service_template(self, config: Dict[str, Any]) -> str:
        return """apiVersion: v1
kind: Service
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "app.selectorLabels" . | nindent 4 }}
"""

    def _generate_ingress_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.ingress.enabled -}}
{{- $fullName := include "app.fullname" . -}}
{{- $svcPort := .Values.service.port -}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ $fullName }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.className }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ $fullName }}
                port:
                  number: {{ $svcPort }}
          {{- end }}
    {{- end }}
{{- end }}
"""

    def _generate_configmap_template(self, config: Dict[str, Any]) -> str:
        return """apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
data:
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
"""

    def _generate_secret_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.secrets }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
type: Opaque
data:
  {{- range $key, $value := .Values.secrets }}
  {{ $key }}: {{ $value | b64enc | quote }}
  {{- end }}
{{- end }}
"""

    def _generate_hpa_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "app.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
{{- end }}
"""

    def _generate_serviceaccount_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "app.serviceAccountName" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
automountServiceAccountToken: {{ .Values.serviceAccount.automount }}
{{- end }}
"""

    def _generate_pvc_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  accessModes:
    - {{ .Values.persistence.accessMode | default "ReadWriteOnce" }}
  {{- if .Values.persistence.storageClass }}
  storageClassName: {{ .Values.persistence.storageClass }}
  {{- end }}
  resources:
    requests:
      storage: {{ .Values.persistence.size }}
{{- end }}
"""

    def _generate_networkpolicy_template(self, config: Dict[str, Any]) -> str:
        return """{{- if .Values.networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "app.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: {{ .Values.service.port }}
  egress:
    - to:
        - podSelector: {}
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
{{- end }}
"""

    def _generate_notes(self, chart_name: str) -> str:
        return f'''Thank you for installing {{{{ .Chart.Name }}}}.

Your release is named {{{{ .Release.Name }}}}.

To learn more about the release, try:

  $ helm status {{{{ .Release.Name }}}}
  $ helm get all {{{{ .Release.Name }}}}

{{{{- if .Values.ingress.enabled }}}}
The application will be available at:
{{{{- range .Values.ingress.hosts }}}}
  http{{{{- if $.Values.ingress.tls }}}}s{{{{- end }}}}://{{{{ .host }}}}
{{{{- end }}}}
{{{{- else }}}}
To access the application, run:

  export POD_NAME=$(kubectl get pods --namespace {{{{ .Release.Namespace }}}} -l "app.kubernetes.io/name={{{{ include "{chart_name}.name" . }}}},app.kubernetes.io/instance={{{{ .Release.Name }}}}" -o jsonpath="{{{{.items[0].metadata.name}}}}")
  kubectl --namespace {{{{ .Release.Namespace }}}} port-forward $POD_NAME 8080:{{{{ .Values.service.port }}}}

Then visit http://localhost:8080
{{{{- end }}}}
'''

    def _combine_files(self, files: Dict[str, str]) -> str:
        output_parts = []
        for filename, content in sorted(files.items()):
            output_parts.append(f"--- # {filename}\n{content}")
        return "\n".join(output_parts)
