import uuid

from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    provider = models.CharField(max_length=50, default="arvancloud")
    provider_config = models.JSONField(default=dict, blank=True)

    settings = models.JSONField(default=dict, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_projects",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["organization", "slug"]

    def __str__(self):
        return f"{self.organization.name}/{self.name}"


class Workspace(BaseModel):
    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        PLANNING = "planning", "Planning"
        APPLYING = "applying", "Applying"
        DESTROYING = "destroying", "Destroying"
        ERROR = "error", "Error"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="workspaces",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IDLE,
    )

    environment = models.CharField(max_length=50, default="development")
    terraform_version = models.CharField(max_length=20, default="1.6.0")
    working_directory = models.CharField(max_length=500, blank=True)

    state_version = models.IntegerField(default=0)
    last_applied_at = models.DateTimeField(null=True, blank=True)

    variables = models.JSONField(default=dict, blank=True)
    sensitive_variables = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["project", "name"]

    def __str__(self):
        return f"{self.project.name}/{self.name}"


class InfrastructureState(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="states",
    )
    version = models.IntegerField()

    state_data = models.JSONField(default=dict)
    resources = models.JSONField(default=list)
    outputs = models.JSONField(default=dict)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    change_summary = models.JSONField(default=dict)

    class Meta:
        ordering = ["-version"]
        unique_together = ["workspace", "version"]

    def __str__(self):
        return f"{self.workspace.name} v{self.version}"


class Deployment(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PLANNING = "planning", "Planning"
        PLANNED = "planned", "Planned"
        APPLYING = "applying", "Applying"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        ROLLED_BACK = "rolled_back", "Rolled Back"

    class DeploymentType(models.TextChoices):
        PLAN = "plan", "Plan"
        APPLY = "apply", "Apply"
        DESTROY = "destroy", "Destroy"
        REFRESH = "refresh", "Refresh"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="deployments",
    )
    deployment_type = models.CharField(
        max_length=20,
        choices=DeploymentType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    plan_output = models.TextField(blank=True)
    apply_output = models.TextField(blank=True)
    changes = models.JSONField(default=dict)

    error_message = models.TextField(blank=True)
    can_retry = models.BooleanField(default=True)

    agent_session_id = models.UUIDField(null=True, blank=True)
    agent_decisions = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.workspace.name} - {self.deployment_type} ({self.status})"


class AgentSession(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="agent_sessions",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    task_description = models.TextField()
    workflow_type = models.CharField(max_length=50, blank=True)

    agents_used = models.JSONField(default=list)
    thoughts = models.JSONField(default=list)
    actions = models.JSONField(default=list)

    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    llm_tokens_used = models.IntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {self.id} - {self.status}"


class ChatMessage(BaseModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        TOOL = "tool", "Tool"

    session = models.ForeignKey(
        AgentSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()

    agent_name = models.CharField(max_length=100, blank=True)
    tool_name = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
