from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Confidence(float, Enum):
    VERY_HIGH = 0.95
    HIGH = 0.85
    MEDIUM = 0.70
    LOW = 0.50
    VERY_LOW = 0.30
    UNKNOWN = 0.0


@dataclass
class LearnerResult:
    learner_name: str
    output: Any
    confidence: float
    reasoning: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_confident(self) -> bool:
        return self.confidence >= Confidence.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learner": self.learner_name,
            "output": self.output,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "sources": self.sources,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Query:
    id: str
    text: str
    query_type: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseLearner(ABC):
    name: str = "base"
    is_weak: bool = True

    @abstractmethod
    async def process(self, query: Query) -> LearnerResult:
        pass

    @abstractmethod
    def can_handle(self, query: Query) -> bool:
        pass

    def estimate_latency(self, query: Query) -> float:
        return 1000.0 if self.is_weak else 5000.0

    def estimate_cost(self, query: Query) -> float:
        return 0.0 if self.is_weak else 1.0
