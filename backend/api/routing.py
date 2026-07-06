from django.urls import path

from api.consumers import AgentSessionConsumer, DeploymentConsumer

websocket_urlpatterns = [
    path("ws/agent/<str:session_id>/", AgentSessionConsumer.as_asgi()),
    path("ws/deployment/<str:deployment_id>/", DeploymentConsumer.as_asgi()),
]
