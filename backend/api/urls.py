from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    DeepAgentChatView,
    DeepAgentStreamView,
    DeploymentViewSet,
    HealthCheckView,
    ProjectAnalyzeView,
    ProjectViewSet,
    QuickActionsView,
    SessionViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register(r"sessions", SessionViewSet, basename="session")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"workspaces", WorkspaceViewSet, basename="workspace")
router.register(r"deployments", DeploymentViewSet, basename="deployment")

quick_actions = QuickActionsView.as_view()

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("chat/", DeepAgentChatView.as_view(), name="chat"),
    path("chat/stream/", DeepAgentStreamView.as_view(), name="chat-stream"),
    path("generate/", quick_actions, {"action": "generate"}, name="generate"),
    path(
        "security/scan/",
        quick_actions,
        {"action": "security_scan"},
        name="security-scan",
    ),
    path(
        "cost/estimate/",
        quick_actions,
        {"action": "cost_estimate"},
        name="cost-estimate",
    ),
    path("diagnose/", quick_actions, {"action": "diagnose"}, name="diagnose"),
    path("projects/analyze/", ProjectAnalyzeView.as_view(), name="project-analyze"),
    path("", include(router.urls)),
]
