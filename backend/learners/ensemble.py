import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from learners.base import BaseLearner, Confidence, LearnerResult, Query
from learners.weak import RuleBasedLearner, CacheLearner, StatisticalLearner
from learners.strong import LLMLearner, RAGLearner

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    strategy: str
    learners: List[str]
    reasoning: str
    estimated_latency_ms: float
    estimated_cost: float


class AdaptiveRouter:
    COMPLEXITY_THRESHOLD_LOW = 0.3
    COMPLEXITY_THRESHOLD_HIGH = 0.7
    CONFIDENCE_THRESHOLD = 0.7
    LATENCY_CONSTRAINT_FAST = 1000

    def __init__(self):
        self._performance_history: Dict[str, List[float]] = {}

    def route(self, query: Query, learners: Dict[str, BaseLearner]) -> RoutingDecision:
        complexity = self._estimate_complexity(query)

        constraints = query.constraints
        max_latency = constraints.get("max_latency_ms", 10000)
        min_confidence = constraints.get("min_confidence", 0.5)
        constraints.get("max_cost", float("inf"))

        weak_learners = [name for name, l in learners.items() if l.is_weak]
        strong_learners = [name for name, l in learners.items() if not l.is_weak]

        if (
            complexity < self.COMPLEXITY_THRESHOLD_LOW
            and max_latency < self.LATENCY_CONSTRAINT_FAST
        ):
            return RoutingDecision(
                strategy="weak_only",
                learners=weak_learners,
                reasoning="Low complexity query with tight latency constraint",
                estimated_latency_ms=100,
                estimated_cost=0,
            )

        if (
            complexity > self.COMPLEXITY_THRESHOLD_HIGH
            or min_confidence > self.CONFIDENCE_THRESHOLD
        ):
            return RoutingDecision(
                strategy="strong_only",
                learners=strong_learners[:1],
                reasoning="High complexity or confidence requirement",
                estimated_latency_ms=5000,
                estimated_cost=1.0,
            )

        return RoutingDecision(
            strategy="cascade",
            learners=weak_learners + strong_learners,
            reasoning="Medium complexity, will cascade from weak to strong if needed",
            estimated_latency_ms=500,
            estimated_cost=0.2,
        )

    def _estimate_complexity(self, query: Query) -> float:
        score = 0.0

        text_len = len(query.text)
        if text_len > 500:
            score += 0.3
        elif text_len > 200:
            score += 0.15

        if query.context:
            context_size = len(str(query.context))
            if context_size > 2000:
                score += 0.3
            elif context_size > 500:
                score += 0.15

        complex_types = ["planning", "diagnostic", "migration"]
        if query.query_type in complex_types:
            score += 0.2

        if query.constraints:
            score += min(0.2, len(query.constraints) * 0.05)

        return min(1.0, score)

    def record_performance(self, learner_name: str, latency_ms: float) -> None:
        if learner_name not in self._performance_history:
            self._performance_history[learner_name] = []

        self._performance_history[learner_name].append(latency_ms)

        if len(self._performance_history[learner_name]) > 100:
            self._performance_history[learner_name] = self._performance_history[
                learner_name
            ][-100:]


class EnsembleLearner:
    def __init__(
        self,
        weak_learners: Optional[List[BaseLearner]] = None,
        strong_learners: Optional[List[BaseLearner]] = None,
    ):
        self.weak_learners = weak_learners or [
            RuleBasedLearner(),
            CacheLearner(),
            StatisticalLearner(),
        ]

        self.strong_learners = strong_learners or [
            LLMLearner(),
            RAGLearner(),
        ]

        self.all_learners = {
            **{l.name: l for l in self.weak_learners},
            **{l.name: l for l in self.strong_learners},
        }

        self.router = AdaptiveRouter()
        self.cache_learner = next(
            (l for l in self.weak_learners if isinstance(l, CacheLearner)), None
        )

    async def process(
        self,
        query: Query,
        strategy: Optional[str] = None,
    ) -> LearnerResult:
        datetime.utcnow()

        if strategy:
            decision = RoutingDecision(
                strategy=strategy,
                learners=list(self.all_learners.keys()),
                reasoning=f"Strategy override: {strategy}",
                estimated_latency_ms=0,
                estimated_cost=0,
            )
        else:
            decision = self.router.route(query, self.all_learners)

        logger.info(f"Routing decision: {decision.strategy} - {decision.reasoning}")

        if decision.strategy == "weak_only":
            result = await self._execute_weak_only(query, decision.learners)

        elif decision.strategy == "strong_only":
            result = await self._execute_strong_only(query, decision.learners)

        elif decision.strategy == "cascade":
            result = await self._execute_cascade(query, decision.learners)

        else:
            result = await self._execute_ensemble(query, decision.learners)

        if result.is_confident and self.cache_learner:
            await self.cache_learner.store(query, result)

        self.router.record_performance(result.learner_name, result.latency_ms)

        return result

    async def _execute_weak_only(
        self,
        query: Query,
        learner_names: List[str],
    ) -> LearnerResult:
        learners = [
            self.all_learners[name]
            for name in learner_names
            if name in self.all_learners and self.all_learners[name].can_handle(query)
        ]

        if not learners:
            return LearnerResult(
                learner_name="ensemble",
                output=None,
                confidence=Confidence.UNKNOWN,
                reasoning="No applicable weak learners",
            )

        tasks = [l.process(query) for l in learners]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [
            r
            for r in results
            if isinstance(r, LearnerResult) and r.confidence > Confidence.UNKNOWN
        ]

        if not valid_results:
            return LearnerResult(
                learner_name="ensemble",
                output=None,
                confidence=Confidence.UNKNOWN,
                reasoning="All weak learners returned low confidence",
            )

        return max(valid_results, key=lambda r: r.confidence)

    async def _execute_strong_only(
        self,
        query: Query,
        learner_names: List[str],
    ) -> LearnerResult:
        for name in learner_names:
            if name in self.all_learners:
                learner = self.all_learners[name]
                if not learner.is_weak and learner.can_handle(query):
                    return await learner.process(query)

        return await LLMLearner().process(query)

    async def _execute_cascade(
        self,
        query: Query,
        learner_names: List[str],
    ) -> LearnerResult:
        weak_result = await self._execute_weak_only(
            query,
            [n for n in learner_names if self.all_learners.get(n, {}).is_weak],
        )

        if weak_result.confidence >= Confidence.MEDIUM:
            return weak_result

        logger.info(
            f"Weak learners not confident ({weak_result.confidence}), escalating to strong"
        )

        strong_learners = [
            n
            for n in learner_names
            if n in self.all_learners and not self.all_learners[n].is_weak
        ]

        return await self._execute_strong_only(query, strong_learners)

    async def _execute_ensemble(
        self,
        query: Query,
        learner_names: List[str],
    ) -> LearnerResult:
        learners = [
            self.all_learners[name]
            for name in learner_names
            if name in self.all_learners and self.all_learners[name].can_handle(query)
        ]

        tasks = [l.process(query) for l in learners]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [
            r
            for r in results
            if isinstance(r, LearnerResult) and r.confidence > Confidence.UNKNOWN
        ]

        if not valid_results:
            return LearnerResult(
                learner_name="ensemble",
                output=None,
                confidence=Confidence.UNKNOWN,
                reasoning="No valid results from ensemble",
            )

        return self._combine_results(valid_results)

    def _combine_results(self, results: List[LearnerResult]) -> LearnerResult:
        best = max(results, key=lambda r: r.confidence)

        return LearnerResult(
            learner_name=f"ensemble({best.learner_name})",
            output=best.output,
            confidence=best.confidence,
            reasoning=f"Best of {len(results)} learners: {best.reasoning}",
            sources=best.sources,
            latency_ms=max(r.latency_ms for r in results),
            tokens_used=sum(r.tokens_used for r in results),
        )
