from rest_framework import serializers

from core.models import (
    AgentSession,
    ChatMessage,
    Deployment,
    InfrastructureState,
    Organization,
    Project,
    Workspace,
)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name",
        read_only=True,
    )
    workspace_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "organization",
            "organization_name",
            "name",
            "slug",
            "description",
            "status",
            "provider",
            "provider_config",
            "settings",
            "owner",
            "workspace_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_workspace_count(self, obj):
        return obj.workspaces.count()


class WorkspaceSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )
    latest_deployment = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "description",
            "status",
            "environment",
            "terraform_version",
            "working_directory",
            "state_version",
            "last_applied_at",
            "variables",
            "latest_deployment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state_version",
            "last_applied_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "sensitive_variables": {"write_only": True},
        }

    def get_latest_deployment(self, obj):
        deployment = obj.deployments.first()
        if deployment:
            return {
                "id": str(deployment.id),
                "type": deployment.deployment_type,
                "status": deployment.status,
                "created_at": deployment.created_at.isoformat(),
            }
        return None


class InfrastructureStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfrastructureState
        fields = [
            "id",
            "workspace",
            "version",
            "state_data",
            "resources",
            "outputs",
            "created_by",
            "change_summary",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DeploymentSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(
        source="workspace.name",
        read_only=True,
    )
    triggered_by_name = serializers.CharField(
        source="triggered_by.username",
        read_only=True,
    )
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = [
            "id",
            "workspace",
            "workspace_name",
            "deployment_type",
            "status",
            "triggered_by",
            "triggered_by_name",
            "started_at",
            "completed_at",
            "duration",
            "plan_output",
            "apply_output",
            "changes",
            "error_message",
            "can_retry",
            "agent_session_id",
            "agent_decisions",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "started_at",
            "completed_at",
            "plan_output",
            "apply_output",
            "changes",
            "error_message",
            "agent_session_id",
            "agent_decisions",
            "created_at",
        ]

    def get_duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return delta.total_seconds()
        return None


class AgentSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = [
            "id",
            "project",
            "user",
            "status",
            "task_description",
            "workflow_type",
            "agents_used",
            "thoughts",
            "actions",
            "result",
            "error",
            "started_at",
            "completed_at",
            "duration",
            "message_count",
            "llm_tokens_used",
            "estimated_cost",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "started_at",
            "completed_at",
            "llm_tokens_used",
            "estimated_cost",
            "created_at",
        ]

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return delta.total_seconds()
        return None


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "role",
            "content",
            "agent_name",
            "tool_name",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InfrastructurePlanSerializer(serializers.Serializer):
    description = serializers.CharField(
        help_text="Natural language description of infrastructure",
    )
    provider = serializers.ChoiceField(
        choices=["arvancloud", "aws", "gcp", "azure"],
        default="arvancloud",
    )
    environment = serializers.ChoiceField(
        choices=["development", "staging", "production"],
        default="development",
    )
    options = serializers.JSONField(
        required=False,
        default=dict,
    )


class SecurityScanSerializer(serializers.Serializer):
    configuration = serializers.CharField(
        help_text="Infrastructure configuration to scan",
    )
    standards = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=["CIS"],
    )


class CostEstimateSerializer(serializers.Serializer):
    configuration = serializers.CharField(
        help_text="Infrastructure configuration to estimate",
    )
    provider = serializers.ChoiceField(
        choices=["arvancloud", "aws", "gcp", "azure"],
        default="arvancloud",
    )
    duration_months = serializers.IntegerField(
        default=1,
        min_value=1,
        max_value=36,
    )
