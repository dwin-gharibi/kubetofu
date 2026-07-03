import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    metric: Dict[str, str]
    values: List[Tuple[float, str]]


@dataclass
class AlertRule:
    name: str
    expr: str
    duration: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    state: str


class PrometheusIntegration:
    def __init__(self, url: Optional[str] = None):
        self.url = url or os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

    async def query(
        self,
        query: str,
        time: Optional[datetime] = None,
    ) -> List[MetricResult]:
        params = {"query": query}
        if time:
            params["time"] = time.timestamp()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/v1/query",
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"Prometheus query failed: {response.status_code}")
                    return []

                data = response.json()

                if data["status"] != "success":
                    return []

                results = []
                for result in data["data"]["result"]:
                    metric_result = MetricResult(
                        metric=result["metric"],
                        values=[(result["value"][0], result["value"][1])],
                    )
                    results.append(metric_result)

                return results

        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            return []

    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> List[MetricResult]:
        params = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/v1/query_range",
                    params=params,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()

                if data["status"] != "success":
                    return []

                results = []
                for result in data["data"]["result"]:
                    metric_result = MetricResult(
                        metric=result["metric"],
                        values=[(v[0], v[1]) for v in result["values"]],
                    )
                    results.append(metric_result)

                return results

        except Exception as e:
            logger.error(f"Prometheus range query error: {e}")
            return []

    async def get_node_metrics(self) -> Dict[str, Any]:
        metrics = {}

        cpu_results = await self.query(
            '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
        )
        if cpu_results:
            metrics["cpu_usage"] = {
                r.metric.get("instance", "unknown"): float(r.values[0][1])
                for r in cpu_results
            }

        memory_results = await self.query(
            "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
        )
        if memory_results:
            metrics["memory_usage"] = {
                r.metric.get("instance", "unknown"): float(r.values[0][1])
                for r in memory_results
            }

        disk_results = await self.query(
            '(1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100'
        )
        if disk_results:
            metrics["disk_usage"] = {
                f"{r.metric.get('instance', 'unknown')}:{r.metric.get('mountpoint', '/')}": float(
                    r.values[0][1]
                )
                for r in disk_results
            }

        return metrics

    async def get_pod_metrics(self, namespace: str = "default") -> Dict[str, Any]:
        metrics = {}

        cpu_results = await self.query(
            f'sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))'
        )
        if cpu_results:
            metrics["cpu_usage"] = {
                r.metric.get("pod", "unknown"): float(r.values[0][1])
                for r in cpu_results
            }

        memory_results = await self.query(
            f'sum by (pod) (container_memory_working_set_bytes{{namespace="{namespace}"}})'
        )
        if memory_results:
            metrics["memory_usage"] = {
                r.metric.get("pod", "unknown"): float(r.values[0][1])
                for r in memory_results
            }

        return metrics

    async def get_alerts(self) -> List[AlertRule]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/v1/alerts",
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()

                if data["status"] != "success":
                    return []

                alerts = []
                for alert in data["data"]["alerts"]:
                    rule = AlertRule(
                        name=alert["labels"].get("alertname", ""),
                        expr="",
                        duration="",
                        labels=alert["labels"],
                        annotations=alert.get("annotations", {}),
                        state=alert["state"],
                    )
                    alerts.append(rule)

                return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/-/healthy",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
