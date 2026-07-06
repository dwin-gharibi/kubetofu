import asyncio
import json
import logging
import uuid
from datetime import datetime

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from agents.langchain.deep_agent import DeepAgent, create_deep_agent
from api.serializers import (
    DeploymentSerializer,
    ProjectSerializer,
    WorkspaceSerializer,
)
from core.models import (
    AgentSession,
    ChatMessage,
    Deployment,
    Project,
    Workspace,
)

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "status": "healthy",
                "service": "kube-tofu-api",
                "version": "2.0.0",
                "timestamp": datetime.utcnow().isoformat(),
                "features": {
                    "deep_agent": True,
                    "streaming": True,
                    "tool_calling": True,
                    "sub_agents": True,
                    "sessions": True,
                },
            }
        )


class SessionViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        sessions = AgentSession.objects.all().order_by("-created_at")[:50]

        data = [
            {
                "id": str(session.id),
                "title": session.task_description[:50]
                if session.task_description
                else "گفتگوی جدید",
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "messages_count": session.messages.count(),
                "agents_used": session.agents_used,
            }
            for session in sessions
        ]

        return Response(data)

    def create(self, request):
        session = AgentSession.objects.create(
            task_description=request.data.get("title", "گفتگوی جدید"),
            status=AgentSession.Status.ACTIVE,
        )

        return Response(
            {
                "id": str(session.id),
                "title": session.task_description,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "messages_count": 0,
                "agents_used": [],
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        session = get_object_or_404(AgentSession, pk=pk)

        return Response(
            {
                "id": str(session.id),
                "title": session.task_description,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "messages_count": session.messages.count(),
                "agents_used": session.agents_used,
                "thoughts": session.thoughts,
                "actions": session.actions,
            }
        )

    def destroy(self, request, pk=None):
        session = get_object_or_404(AgentSession, pk=pk)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        session = get_object_or_404(AgentSession, pk=pk)
        messages = session.messages.all().order_by("created_at")

        data = [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "agent_name": msg.agent_name,
                "tool_name": msg.tool_name,
                "metadata": msg.metadata,
            }
            for msg in messages
        ]

        return Response(data)


class DeepAgentChatView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get("message", "")
        session_id = request.data.get("session_id")
        context = request.data.get("context", {})

        if not message:
            return Response(
                {"error": "پیام نمی‌تواند خالی باشد"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session_id:
            try:
                session = AgentSession.objects.get(pk=session_id)
            except AgentSession.DoesNotExist:
                session = AgentSession.objects.create(
                    id=session_id,
                    task_description=message[:100],
                    status=AgentSession.Status.ACTIVE,
                )
        else:
            session = AgentSession.objects.create(
                task_description=message[:100],
                status=AgentSession.Status.ACTIVE,
            )

        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.USER,
            content=message,
        )

        try:
            agent = DeepAgent(
                name="KubeTofuAgent",
                description="عامل هوشمند کیوب‌توفو برای مدیریت زیرساخت",
                session_id=str(session.id),
                agent_type="general",
                enable_shell=True,
                enable_human_in_loop=True,
                enable_memory=True,
            )

            result = asyncio.run(agent.run(message, context=context))

            if result.success:
                ChatMessage.objects.create(
                    session=session,
                    role=ChatMessage.Role.ASSISTANT,
                    content=result.output,
                    metadata={
                        "thoughts": result.thoughts,
                        "actions": result.actions,
                    },
                )

                session.agents_used = list(set(session.agents_used + ["KubeTofuAgent"]))
                session.thoughts = result.thoughts
                session.actions = result.actions
                session.save()

                return Response(
                    {
                        "response": result.output,
                        "session_id": str(session.id),
                        "thoughts": result.thoughts,
                        "actions": result.actions,
                        "agents_used": session.agents_used,
                        "metadata": {
                            "metrics": result.metrics.to_dict()
                            if result.metrics
                            else None,
                        },
                    }
                )
            else:
                return Response(
                    {
                        "error": result.error or "خطا در پردازش درخواست",
                        "session_id": str(session.id),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.exception(f"Deep agent chat failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(csrf_exempt, name="dispatch")
class DeepAgentStreamView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get("message", "")
        session_id = request.data.get("session_id")
        context = request.data.get("context", {})

        if not message:
            return Response(
                {"error": "پیام نمی‌تواند خالی باشد"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def event_stream():
            try:
                if session_id:
                    try:
                        session = AgentSession.objects.get(pk=session_id)
                    except AgentSession.DoesNotExist:
                        session = AgentSession.objects.create(
                            task_description=message[:100],
                            status=AgentSession.Status.ACTIVE,
                        )
                else:
                    session = AgentSession.objects.create(
                        task_description=message[:100],
                        status=AgentSession.Status.ACTIVE,
                    )

                ChatMessage.objects.create(
                    session=session,
                    role=ChatMessage.Role.USER,
                    content=message,
                )

                project_context = ""
                if context:
                    project_name = context.get("project_name", "")
                    if project_name:
                        project_context = f"\n\n## اطلاعات پروژه: {project_name}\n"
                        if context.get("language"):
                            project_context += f"- زبان: {context.get('language')}\n"
                        if context.get("framework"):
                            project_context += (
                                f"- فریم‌ورک: {context.get('framework')}\n"
                            )
                        if context.get("service_type"):
                            project_context += (
                                f"- نوع سرویس: {context.get('service_type')}\n"
                            )
                        if context.get("databases"):
                            project_context += f"- دیتابیس‌ها: {', '.join(context.get('databases', []))}\n"
                        project_context += f"- Dockerfile: {'موجود' if context.get('has_dockerfile') else 'ندارد'}\n"
                        project_context += f"- Kubernetes: {'موجود' if context.get('has_kubernetes') else 'ندارد'}\n"
                        project_context += f"- Terraform: {'موجود' if context.get('has_terraform') else 'ندارد'}\n"

                        if context.get("files"):
                            files = context.get("files", [])[:10]  # Limit to 10 files
                            project_context += f"- فایل‌های اصلی: {', '.join(f.get('name', '') for f in files)}\n"

                enhanced_message = message
                if project_context:
                    enhanced_message = f"{message}\n{project_context}"

                agent = DeepAgent(
                    name="KubeTofuAgent",
                    description="عامل هوشمند کیوب‌توفو برای مدیریت زیرساخت",
                    session_id=str(session.id),
                    agent_type="general",
                )

                thinking_message = "در حال تحلیل درخواست..."
                if context and context.get("project_name"):
                    thinking_message = (
                        f'در حال تحلیل پروژه "{context.get("project_name")}"...'
                    )

                yield f"data: {json.dumps({'type': 'agent_event', 'agent': {'type': 'agent_thinking', 'agent_name': 'برنامه‌ریز', 'message': thinking_message}})}\n\n"

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    full_response = ""
                    response_holder = {"content": ""}

                    async def run_agent():
                        nonlocal response_holder
                        async for event in agent.stream(
                            enhanced_message, context=context
                        ):
                            event_type = event.get("event")

                            if event_type == "on_tool_start":
                                tool_name = event.get("name", "")
                                tool_input = event.get("data", {}).get("input", {})
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': {'type': 'tool_start', 'tool_name': tool_name, 'tool_input': tool_input}})}\n\n"

                            elif event_type == "on_tool_end":
                                tool_name = event.get("name", "")
                                tool_output = str(
                                    event.get("data", {}).get("output", "")
                                )[:500]
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': {'type': 'tool_end', 'tool_name': tool_name, 'tool_output': tool_output}})}\n\n"

                            elif event_type == "on_llm_stream":
                                content = (
                                    event.get("data", {})
                                    .get("chunk", {})
                                    .get("content", "")
                                )
                                if content:
                                    response_holder["content"] += content
                                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                            elif event_type == "on_chain_end":
                                output = event.get("data", {}).get("output", "")
                                if output and not response_holder["content"]:
                                    response_holder["content"] = str(output)

                    gen = run_agent()
                    while True:
                        try:
                            event = loop.run_until_complete(gen.__anext__())
                            yield event
                        except StopAsyncIteration:
                            break

                    full_response = response_holder["content"]

                    if full_response:
                        ChatMessage.objects.create(
                            session=session,
                            role=ChatMessage.Role.ASSISTANT,
                            content=full_response,
                        )

                        yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'session_id': str(session.id)})}\n\n"

                finally:
                    loop.close()

            except Exception as e:
                logger.exception(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class QuickActionsView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, action=None):
        if action == "generate":
            return self.generate(request)
        elif action == "security_scan":
            return self.security_scan(request)
        elif action == "cost_estimate":
            return self.cost_estimate(request)
        elif action == "diagnose":
            return self.diagnose(request)

        return Response(
            {"error": "Unknown action"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def generate(self, request):
        description = request.data.get("description", "")
        format_type = request.data.get("format", "auto")
        provider = request.data.get("provider", "arvancloud")

        if not description:
            return Response(
                {"error": "توضیحات نمی‌تواند خالی باشد"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agent = create_deep_agent(
                agent_type="planner",
                session_id=str(uuid.uuid4()),
            )

            prompt = f"کد {format_type} برای این نیاز تولید کن:\n{description}\n\nارائه‌دهنده: {provider}"
            result = asyncio.run(agent.run(prompt))

            return Response(
                {
                    "success": result.success,
                    "code": result.output if result.success else None,
                    "error": result.error,
                    "format": format_type,
                    "provider": provider,
                }
            )

        except Exception as e:
            logger.exception(f"Generate failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def security_scan(self, request):
        code = request.data.get("code", "")
        code_type = request.data.get("type", "auto")

        if not code:
            return Response(
                {"error": "کد نمی‌تواند خالی باشد"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agent = create_deep_agent(
                agent_type="security",
                session_id=str(uuid.uuid4()),
            )

            prompt = f"این کد {code_type} را از نظر امنیتی بررسی کن:\n\n```{code_type}\n{code}\n```"
            result = asyncio.run(agent.run(prompt))

            return Response(
                {
                    "success": result.success,
                    "analysis": result.output if result.success else None,
                    "error": result.error,
                }
            )

        except Exception as e:
            logger.exception(f"Security scan failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def cost_estimate(self, request):
        code = request.data.get("code", "")
        provider = request.data.get("provider", "arvancloud")

        if not code:
            return Response(
                {"error": "کد نمی‌تواند خالی باشد"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agent = create_deep_agent(
                agent_type="cost",
                session_id=str(uuid.uuid4()),
            )

            prompt = f"هزینه این پیکربندی را برای ارائه‌دهنده {provider} تخمین بزن:\n\n```\n{code}\n```"
            result = asyncio.run(agent.run(prompt))

            return Response(
                {
                    "success": result.success,
                    "estimate": result.output if result.success else None,
                    "error": result.error,
                }
            )

        except Exception as e:
            logger.exception(f"Cost estimate failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def diagnose(self, request):
        namespace = request.data.get("namespace", "default")
        resource_type = request.data.get("resource_type", "all")
        resource_name = request.data.get("resource_name", "")

        try:
            agent = create_deep_agent(
                agent_type="diagnostic",
                session_id=str(uuid.uuid4()),
            )

            prompt = f"مشکلات این منبع کوبرنتیز را بررسی کن:\nNamespace: {namespace}\nنوع: {resource_type}\nنام: {resource_name or 'همه'}"
            result = asyncio.run(agent.run(prompt))

            return Response(
                {
                    "success": result.success,
                    "diagnosis": result.output if result.success else None,
                    "error": result.error,
                }
            )

        except Exception as e:
            logger.exception(f"Diagnose failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProjectAnalyzeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name", "")
        language = request.data.get("language", "unknown")
        framework = request.data.get("framework", "")
        files = request.data.get("files", [])

        if not name:
            return Response(
                {"error": "نام پروژه الزامی است"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agent = create_deep_agent(
                agent_type="planner",
                session_id=str(uuid.uuid4()),
            )

            file_list = ", ".join(f.get("name", "") for f in files[:20])
            prompt = f"""پروژه "{name}" را تحلیل کن:
- زبان: {language}
- فریم‌ورک: {framework}
- فایل‌ها: {file_list}

توصیه‌های IaC ارائه بده:
1. چه Dockerfile ای مناسب است؟
2. چه تنظیمات Kubernetes نیاز است؟
3. چه منابع Terraform باید تعریف شود؟
"""

            result = asyncio.run(agent.run(prompt))

            return Response(
                {
                    "success": result.success,
                    "analysis": result.output if result.success else None,
                    "recommendations": {
                        "dockerfile": language != "unknown",
                        "kubernetes": True,
                        "terraform": True,
                    },
                    "error": result.error,
                }
            )

        except Exception as e:
            logger.exception(f"Project analysis failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Project.objects.all()


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Workspace.objects.all()


class DeploymentViewSet(viewsets.ModelViewSet):
    serializer_class = DeploymentSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Deployment.objects.all()
