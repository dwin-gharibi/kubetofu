import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class SlackIntegration:
    def __init__(self, webhook_url: Optional[str] = None, token: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self.token = token or os.environ.get("SLACK_BOT_TOKEN", "")

    async def send_webhook(
        self,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = attachments

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    async def send_deployment_notification(
        self,
        project: str,
        environment: str,
        status: str,
        details: Optional[str] = None,
        user: Optional[str] = None,
    ) -> bool:
        status_emoji = {
            "started": "🚀",
            "completed": "✅",
            "failed": "❌",
            "pending": "⏳",
        }.get(status, "📋")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Deployment {status.title()}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Project:*\n{project}"},
                    {"type": "mrkdwn", "text": f"*Environment:*\n{environment}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{status.title()}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                    },
                ],
            },
        ]

        if details:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Details:*\n```{details}```"},
                }
            )

        if user:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"Initiated by: {user}"}],
                }
            )

        return await self.send_webhook(
            text=f"Deployment {status} for {project} ({environment})",
            blocks=blocks,
        )

    async def send_security_alert(
        self,
        title: str,
        severity: str,
        description: str,
        resource: str,
        recommendation: Optional[str] = None,
    ) -> bool:
        severity_colors = {
            "critical": "#FF0000",
            "high": "#FF6B00",
            "medium": "#FFB800",
            "low": "#00C853",
        }

        severity_emoji = {
            "critical": "🚨",
            "high": "🔴",
            "medium": "🟠",
            "low": "🟡",
        }.get(severity, "⚠️")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} Security Alert: {title}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Resource:*\n{resource}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n{description}"},
            },
        ]

        if recommendation:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommendation:*\n{recommendation}",
                    },
                }
            )

        attachments = [{"color": severity_colors.get(severity, "#808080")}]

        return await self.send_webhook(
            text=f"Security Alert: {title} ({severity})",
            blocks=blocks,
            attachments=attachments,
        )

    async def send_cost_alert(
        self,
        message: str,
        current_cost: float,
        threshold: float,
        currency: str = "USD",
        breakdown: Optional[Dict[str, float]] = None,
    ) -> bool:
        overage = ((current_cost - threshold) / threshold) * 100

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💰 Cost Alert",
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Cost:*\n{current_cost:,.2f} {currency}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Threshold:*\n{threshold:,.2f} {currency}",
                    },
                    {"type": "mrkdwn", "text": f"*Overage:*\n{overage:.1f}%"},
                ],
            },
        ]

        if breakdown:
            breakdown_text = "\n".join(
                [f"• {k}: {v:,.2f} {currency}" for k, v in breakdown.items()]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Breakdown:*\n{breakdown_text}",
                    },
                }
            )

        return await self.send_webhook(
            text=f"Cost Alert: {message}",
            blocks=blocks,
            attachments=[{"color": "#FF6B00"}],
        )
