import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from django.core.cache import cache
from learners.base import BaseLearner, Confidence, LearnerResult, Query

logger = logging.getLogger(__name__)


class RuleBasedLearner(BaseLearner):
    name = "rule_based"
    is_weak = True

    SECURITY_RULES = [
        {
            "pattern": r"0\.0\.0\.0/0.*:22",
            "severity": "critical",
            "message": "SSH port open to the internet",
            "recommendation": "Restrict SSH to specific IP ranges",
        },
        {
            "pattern": r"0\.0\.0\.0/0.*:(3306|5432|27017|6379)",
            "severity": "critical",
            "message": "Database port open to the internet",
            "recommendation": "Place databases in private subnets",
        },
        {
            "pattern": r"password\s*=\s*['\"][^'\"]+['\"]",
            "severity": "critical",
            "message": "Hardcoded password detected",
            "recommendation": "Use secrets management",
        },
        {
            "pattern": r"encrypted\s*=\s*false",
            "severity": "high",
            "message": "Encryption disabled",
            "recommendation": "Enable encryption for storage",
        },
        {
            "pattern": r"privileged\s*[=:]\s*true",
            "severity": "high",
            "message": "Privileged container detected",
            "recommendation": "Avoid privileged mode",
        },
    ]

    COST_RULES = [
        {
            "pattern": r"(g2|m5|c5)\-(8|16|32)",
            "category": "oversized",
            "message": "Large instance detected",
            "recommendation": "Consider smaller instances with auto-scaling",
            "potential_savings_percent": 30,
        },
        {
            "pattern": r"count\s*=\s*([5-9]|[1-9]\d+)",
            "category": "high_count",
            "message": "High resource count detected",
            "recommendation": "Consider auto-scaling instead of fixed count",
            "potential_savings_percent": 25,
        },
    ]

    BEST_PRACTICE_RULES = [
        {
            "pattern": r"tags\s*=",
            "check": "present",
            "message": "Resource tagging configured",
            "passed": True,
        },
        {
            "pattern": r"description\s*=",
            "check": "present",
            "message": "Descriptions provided",
            "passed": True,
        },
        {
            "pattern": r"lifecycle\s*{",
            "check": "present",
            "message": "Lifecycle rules configured",
            "passed": True,
        },
    ]

    def can_handle(self, query: Query) -> bool:
        return query.query_type in ["security", "cost", "evaluation"]

    async def process(self, query: Query) -> LearnerResult:
        start_time = datetime.utcnow()

        text = query.text
        context = query.context
        configuration = context.get("configuration", text)

        results = {}
        confidence = Confidence.LOW

        if query.query_type == "security":
            results = self._check_security_rules(configuration)
            if results.get("issues"):
                confidence = Confidence.HIGH
            else:
                confidence = Confidence.MEDIUM

        elif query.query_type == "cost":
            results = self._check_cost_rules(configuration)
            if results.get("optimizations"):
                confidence = Confidence.MEDIUM
            else:
                confidence = Confidence.LOW

        elif query.query_type == "evaluation":
            results = self._check_best_practices(configuration)
            confidence = Confidence.MEDIUM

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return LearnerResult(
            learner_name=self.name,
            output=results,
            confidence=confidence,
            reasoning="Pattern matching against predefined rules",
            latency_ms=latency,
        )

    def _check_security_rules(self, config: str) -> Dict[str, Any]:
        issues = []

        for rule in self.SECURITY_RULES:
            if re.search(rule["pattern"], config, re.IGNORECASE):
                issues.append(
                    {
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "recommendation": rule["recommendation"],
                    }
                )

        return {
            "issues": issues,
            "issue_count": len(issues),
            "has_critical": any(i["severity"] == "critical" for i in issues),
        }

    def _check_cost_rules(self, config: str) -> Dict[str, Any]:
        optimizations = []

        for rule in self.COST_RULES:
            if re.search(rule["pattern"], config, re.IGNORECASE):
                optimizations.append(
                    {
                        "category": rule["category"],
                        "message": rule["message"],
                        "recommendation": rule["recommendation"],
                        "potential_savings_percent": rule["potential_savings_percent"],
                    }
                )

        return {
            "optimizations": optimizations,
            "optimization_count": len(optimizations),
        }

    def _check_best_practices(self, config: str) -> Dict[str, Any]:
        checks = []

        for rule in self.BEST_PRACTICE_RULES:
            found = bool(re.search(rule["pattern"], config, re.IGNORECASE))
            passed = found if rule["check"] == "present" else not found

            checks.append(
                {
                    "message": rule["message"],
                    "passed": passed,
                }
            )

        passed_count = sum(1 for c in checks if c["passed"])

        return {
            "checks": checks,
            "passed": passed_count,
            "total": len(checks),
            "score": (passed_count / len(checks) * 100) if checks else 100,
        }


class CacheLearner(BaseLearner):
    name = "cache"
    is_weak = True
    CACHE_TTL = 3600

    def can_handle(self, query: Query) -> bool:
        return True

    async def process(self, query: Query) -> LearnerResult:
        start_time = datetime.utcnow()

        cache_key = self._create_cache_key(query)
        cached = cache.get(cache_key)

        if cached:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            return LearnerResult(
                learner_name=self.name,
                output=cached["output"],
                confidence=cached.get("confidence", Confidence.HIGH),
                reasoning="Retrieved from cache (exact match)",
                latency_ms=latency,
            )

        similar = await self._find_similar(query)

        if similar:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            return LearnerResult(
                learner_name=self.name,
                output=similar["output"],
                confidence=similar["similarity"] * Confidence.HIGH,
                reasoning=f"Retrieved from cache (similarity: {similar['similarity']:.2f})",
                latency_ms=latency,
            )

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        return LearnerResult(
            learner_name=self.name,
            output=None,
            confidence=Confidence.UNKNOWN,
            reasoning="No cache hit",
            latency_ms=latency,
        )

    def _create_cache_key(self, query: Query) -> str:
        key_string = f"{query.query_type}:{query.text[:200]}"
        return f"learner_cache:{hashlib.sha256(key_string.encode()).hexdigest()}"

    async def _find_similar(self, query: Query) -> Optional[Dict[str, Any]]:
        return None

    async def store(self, query: Query, result: LearnerResult) -> None:
        cache_key = self._create_cache_key(query)

        cache.set(
            cache_key,
            {
                "output": result.output,
                "confidence": result.confidence,
                "timestamp": datetime.utcnow().isoformat(),
            },
            timeout=self.CACHE_TTL,
        )


class StatisticalLearner(BaseLearner):
    name = "statistical"
    is_weak = True

    def can_handle(self, query: Query) -> bool:
        return query.query_type in ["monitoring", "diagnostic", "cost"]

    async def process(self, query: Query) -> LearnerResult:
        start_time = datetime.utcnow()

        context = query.context
        metrics = context.get("metrics", {})

        anomalies = []
        confidence = Confidence.LOW

        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                anomaly = self._check_anomaly(metric_name, value)
                if anomaly:
                    anomalies.append(anomaly)

        if anomalies:
            confidence = Confidence.MEDIUM

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return LearnerResult(
            learner_name=self.name,
            output={
                "anomalies": anomalies,
                "anomaly_count": len(anomalies),
            },
            confidence=confidence,
            reasoning="Statistical analysis of metrics",
            latency_ms=latency,
        )

    def _check_anomaly(
        self,
        metric_name: str,
        value: float,
    ) -> Optional[Dict[str, Any]]:
        thresholds = {
            "cpu_percent": (0, 80),
            "memory_percent": (0, 85),
            "disk_percent": (0, 90),
            "error_rate": (0, 5),
            "latency_ms": (0, 1000),
        }

        if metric_name in thresholds:
            min_val, max_val = thresholds[metric_name]

            if value > max_val:
                return {
                    "metric": metric_name,
                    "value": value,
                    "threshold": max_val,
                    "type": "high",
                    "severity": "high" if value > max_val * 1.2 else "medium",
                }
            elif value < min_val:
                return {
                    "metric": metric_name,
                    "value": value,
                    "threshold": min_val,
                    "type": "low",
                    "severity": "medium",
                }

        return None
