import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings

from learners.base import BaseLearner, Confidence, LearnerResult, Query

logger = logging.getLogger(__name__)


class LLMLearner(BaseLearner):
    name = "llm"
    is_weak = False

    def __init__(
        self,
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-20250514",
    ):
        self.provider = provider
        self.model = model
        self._client = None

    def can_handle(self, query: Query) -> bool:
        return True

    async def process(self, query: Query) -> LearnerResult:
        start_time = datetime.utcnow()
        tokens_used = 0

        try:
            prompt = self._build_prompt(query)
            response = await self._call_llm(prompt)
            output = self._parse_response(response, query.query_type)
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return LearnerResult(
                learner_name=self.name,
                output=output,
                confidence=Confidence.HIGH,
                reasoning=f"LLM analysis using {self.model}",
                latency_ms=latency,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.exception(f"LLM learner failed: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return LearnerResult(
                learner_name=self.name,
                output={"error": str(e)},
                confidence=Confidence.UNKNOWN,
                reasoning=f"LLM call failed: {e}",
                latency_ms=latency,
            )

    def _build_prompt(self, query: Query) -> str:
        system_prompts = {
            "security": """You are a security expert analyzing infrastructure configurations.
Identify vulnerabilities, compliance issues, and provide specific remediation steps.
Output JSON with: issues (list), severity_summary, recommendations.""",
            "cost": """You are a cloud cost optimization expert.
Analyze configurations and identify cost savings opportunities.
Output JSON with: current_estimate, optimizations (list), potential_savings.""",
            "planning": """You are an infrastructure architect.
Design scalable, secure, and cost-effective infrastructure.
Output JSON with: architecture, resources (list), terraform_config.""",
            "diagnostic": """You are a Kubernetes expert diagnosing cluster issues.
Analyze the symptoms and provide root cause analysis.
Output JSON with: issues (list), root_causes, remediation_steps.""",
        }

        system = system_prompts.get(
            query.query_type,
            "You are an infrastructure expert. Analyze the query and provide detailed guidance.",
        )

        context_str = ""
        if query.context:
            context_str = f"\n\nContext:\n{query.context}"

        return f"""{system}

Query: {query.text}{context_str}

Provide your analysis in JSON format."""

    async def _call_llm(self, prompt: str) -> str:
        if self.provider == "anthropic":
            import anthropic

            client = anthropic.AsyncAnthropic(
                api_key=settings.LLM_SETTINGS.get("ANTHROPIC_API_KEY")
            )

            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        elif self.provider == "openai":
            import openai

            client = openai.AsyncOpenAI(
                api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY")
            )

            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )

            return response.choices[0].message.content

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _parse_response(self, response: str, query_type: str) -> Dict[str, Any]:
        import json
        import re

        json_match = re.search(r"\{[\s\S]*\}", response)

        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {"response": response}


class RAGLearner(BaseLearner):
    name = "rag"
    is_weak = False

    def __init__(
        self,
        vector_store: Optional[Any] = None,
        llm_learner: Optional[LLMLearner] = None,
    ):
        self.vector_store = vector_store
        self.llm_learner = llm_learner or LLMLearner()

    def can_handle(self, query: Query) -> bool:
        return True

    async def process(self, query: Query) -> LearnerResult:
        start_time = datetime.utcnow()

        retrieved_docs = await self._retrieve(query.text)

        augmented_query = Query(
            id=query.id,
            text=query.text,
            query_type=query.query_type,
            context={
                **query.context,
                "retrieved_documents": retrieved_docs,
            },
            constraints=query.constraints,
        )

        result = await self.llm_learner.process(augmented_query)

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return LearnerResult(
            learner_name=self.name,
            output=result.output,
            confidence=result.confidence,
            reasoning=f"RAG with {len(retrieved_docs)} documents",
            sources=[d.get("source", "") for d in retrieved_docs],
            latency_ms=latency,
            tokens_used=result.tokens_used,
        )

    async def _retrieve(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if self.vector_store is None:
            return []

        try:
            results = await self.vector_store.similarity_search(query, k=k)

            return [
                {
                    "content": r.page_content,
                    "source": r.metadata.get("source", ""),
                    "score": r.metadata.get("score", 0),
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Document retrieval failed: {e}")
            return []
