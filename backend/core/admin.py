from django.contrib import admin
from django.utils.html import format_html

from core.models import (
    AgentSession,
    ChatMessage,
    Deployment,
    InfrastructureState,
    Organization,
    Project,
    Workspace,
)


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0
    fields = ("name", "slug", "status", "provider", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


class WorkspaceInline(admin.TabularInline):
    model = Workspace
    extra = 0
    fields = ("name", "environment", "status", "last_applied_at")
    readonly_fields = ("last_applied_at",)
    show_change_link = True


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("role", "content_preview", "agent_name", "created_at")
    readonly_fields = ("content_preview", "created_at")

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"


class DeploymentInline(admin.TabularInline):
    model = Deployment
    extra = 0
    fields = ("deployment_type", "status", "triggered_by", "started_at", "completed_at")
    readonly_fields = ("started_at", "completed_at")
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "project_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ProjectInline]

    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        ("Status", {"fields": ("is_active",)}),
        ("Settings", {"fields": ("settings",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def project_count(self, obj):
        return obj.projects.count()

    project_count.short_description = "Projects"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "status",
        "provider",
        "owner",
        "workspace_count",
        "created_at",
    )
    list_filter = ("status", "provider", "organization", "created_at")
    search_fields = ("name", "slug", "description", "organization__name")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("organization", "owner")
    inlines = [WorkspaceInline]

    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "organization")}),
        ("Configuration", {"fields": ("status", "provider", "provider_config")}),
        ("Ownership", {"fields": ("owner",)}),
        ("Settings", {"fields": ("settings",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def workspace_count(self, obj):
        return obj.workspaces.count()

    workspace_count.short_description = "Workspaces"


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "environment",
        "status_badge",
        "terraform_version",
        "state_version",
        "last_applied_at",
    )
    list_filter = (
        "status",
        "environment",
        "terraform_version",
        "project__organization",
    )
    search_fields = ("name", "description", "project__name")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "state_version",
        "last_applied_at",
    )
    raw_id_fields = ("project",)
    inlines = [DeploymentInline]

    fieldsets = (
        (None, {"fields": ("name", "description", "project")}),
        (
            "Environment",
            {"fields": ("environment", "terraform_version", "working_directory")},
        ),
        ("Status", {"fields": ("status", "state_version", "last_applied_at")}),
        (
            "Variables",
            {"fields": ("variables", "sensitive_variables"), "classes": ("collapse",)},
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def status_badge(self, obj):
        colors = {
            "idle": "green",
            "planning": "blue",
            "applying": "orange",
            "destroying": "red",
            "error": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(InfrastructureState)
class InfrastructureStateAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "version",
        "resource_count",
        "created_by",
        "created_at",
    )
    list_filter = (
        "workspace__project__organization",
        "workspace__project",
        "created_at",
    )
    search_fields = ("workspace__name", "workspace__project__name")
    readonly_fields = ("id", "created_at", "updated_at", "version")
    raw_id_fields = ("workspace", "created_by")

    fieldsets = (
        (None, {"fields": ("workspace", "version")}),
        (
            "State Data",
            {
                "fields": ("state_data", "resources", "outputs"),
                "classes": ("collapse",),
            },
        ),
        (
            "Changes",
            {
                "fields": ("change_summary", "created_by"),
            },
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def resource_count(self, obj):
        if isinstance(obj.resources, list):
            return len(obj.resources)
        return 0

    resource_count.short_description = "Resources"


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "deployment_type",
        "status_badge",
        "triggered_by",
        "duration",
        "created_at",
    )
    list_filter = ("status", "deployment_type", "workspace__project", "created_at")
    search_fields = ("workspace__name", "workspace__project__name", "error_message")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "completed_at")
    raw_id_fields = ("workspace", "triggered_by")

    fieldsets = (
        (None, {"fields": ("workspace", "deployment_type", "status")}),
        ("Execution", {"fields": ("triggered_by", "started_at", "completed_at")}),
        (
            "Output",
            {
                "fields": ("plan_output", "apply_output", "changes"),
                "classes": ("collapse",),
            },
        ),
        (
            "Errors",
            {"fields": ("error_message", "can_retry"), "classes": ("collapse",)},
        ),
        (
            "Agent",
            {
                "fields": ("agent_session_id", "agent_decisions"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def status_badge(self, obj):
        colors = {
            "pending": "gray",
            "planning": "blue",
            "planned": "cyan",
            "applying": "orange",
            "completed": "green",
            "failed": "red",
            "cancelled": "gray",
            "rolled_back": "purple",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            minutes, seconds = divmod(delta.seconds, 60)
            return f"{minutes}m {seconds}s"
        return "-"

    duration.short_description = "Duration"


@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "task_preview",
        "status_badge",
        "user",
        "agents_used_display",
        "token_cost",
        "created_at",
    )
    list_filter = ("status", "workflow_type", "project", "created_at")
    search_fields = ("id", "task_description", "user__username")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "llm_tokens_used",
        "estimated_cost",
    )
    raw_id_fields = ("project", "user")
    inlines = [ChatMessageInline]

    fieldsets = (
        (None, {"fields": ("task_description", "workflow_type", "status")}),
        ("Context", {"fields": ("project", "user")}),
        (
            "Agent Activity",
            {
                "fields": ("agents_used", "thoughts", "actions"),
                "classes": ("collapse",),
            },
        ),
        ("Results", {"fields": ("result", "error"), "classes": ("collapse",)}),
        ("Timing", {"fields": ("started_at", "completed_at")}),
        ("Cost", {"fields": ("llm_tokens_used", "estimated_cost")}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    short_id.short_description = "ID"

    def task_preview(self, obj):
        return (
            obj.task_description[:50] + "..."
            if len(obj.task_description) > 50
            else obj.task_description
        )

    task_preview.short_description = "Task"

    def status_badge(self, obj):
        colors = {
            "active": "blue",
            "completed": "green",
            "failed": "red",
            "cancelled": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def agents_used_display(self, obj):
        if obj.agents_used:
            return ", ".join(obj.agents_used)
        return "-"

    agents_used_display.short_description = "Agents"

    def token_cost(self, obj):
        if obj.llm_tokens_used > 0:
            return f"{obj.llm_tokens_used:,} tokens (${obj.estimated_cost:.4f})"
        return "-"

    token_cost.short_description = "Tokens/Cost"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "session",
        "role_badge",
        "content_preview",
        "agent_name",
        "created_at",
    )
    list_filter = ("role", "created_at", "session__project")
    search_fields = ("content", "agent_name", "tool_name", "session__id")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("session",)

    fieldsets = (
        (None, {"fields": ("session", "role", "content")}),
        ("Agent/Tool", {"fields": ("agent_name", "tool_name")}),
        (
            "Metadata",
            {
                "fields": ("metadata", "id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    short_id.short_description = "ID"

    def content_preview(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content

    content_preview.short_description = "Content"

    def role_badge(self, obj):
        colors = {
            "user": "blue",
            "assistant": "green",
            "system": "gray",
            "tool": "orange",
        }
        color = colors.get(obj.role, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_role_display(),
        )

    role_badge.short_description = "Role"


admin.site.site_header = "کیوب‌توفو | پنل مدیریت"
admin.site.site_title = "Kube-Tofu Admin"
admin.site.index_title = "مدیریت پلتفرم هوشمند IaC"
