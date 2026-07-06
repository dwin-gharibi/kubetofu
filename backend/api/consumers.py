import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AgentSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"agent_session_{self.session_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "session_id": self.session_id,
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")

        if message_type == "user_message":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "agent_thinking",
                    "message": "Processing your request...",
                },
            )
        elif message_type == "cancel":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "operation_cancelled",
                },
            )

    async def agent_thinking(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "agent_thinking",
                    "message": event.get("message", ""),
                    "agent": event.get("agent", ""),
                }
            )
        )

    async def agent_action(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "agent_action",
                    "action": event.get("action", ""),
                    "tool": event.get("tool", ""),
                    "input": event.get("input", {}),
                }
            )
        )

    async def agent_observation(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "agent_observation",
                    "observation": event.get("observation", ""),
                    "tool": event.get("tool", ""),
                }
            )
        )

    async def agent_response(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "agent_response",
                    "response": event.get("response", ""),
                    "metadata": event.get("metadata", {}),
                }
            )
        )

    async def session_completed(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "session_completed",
                    "result": event.get("result", {}),
                }
            )
        )

    async def session_error(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "session_error",
                    "error": event.get("error", ""),
                }
            )
        )

    async def operation_cancelled(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "operation_cancelled",
                }
            )
        )


class DeploymentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.deployment_id = self.scope["url_route"]["kwargs"]["deployment_id"]
        self.room_group_name = f"deployment_{self.deployment_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "deployment_id": self.deployment_id,
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def deployment_status(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "deployment_status",
                    "status": event.get("status", ""),
                    "message": event.get("message", ""),
                }
            )
        )

    async def deployment_progress(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "deployment_progress",
                    "progress": event.get("progress", 0),
                    "current_step": event.get("current_step", ""),
                    "total_steps": event.get("total_steps", 0),
                }
            )
        )

    async def deployment_output(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "deployment_output",
                    "output": event.get("output", ""),
                    "stream": event.get("stream", "stdout"),
                }
            )
        )

    async def deployment_completed(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "deployment_completed",
                    "result": event.get("result", {}),
                    "outputs": event.get("outputs", {}),
                }
            )
        )

    async def deployment_failed(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "deployment_failed",
                    "error": event.get("error", ""),
                    "can_retry": event.get("can_retry", True),
                }
            )
        )
