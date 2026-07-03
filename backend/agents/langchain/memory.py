import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from langchain.memory import (
    ConversationBufferWindowMemory,
    ConversationSummaryBufferMemory,
    CombinedMemory,
    VectorStoreRetrieverMemory,
)
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    id: str
    content: str
    memory_type: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "importance": self.importance,
        }


@dataclass
class EntityInfo:
    name: str
    entity_type: str
    properties: Dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    mentions: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "properties": self.properties,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "mentions": self.mentions,
        }


class WorkingMemory:
    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        self.max_messages = max_messages
        self._messages: List[BaseMessage] = []
        self._context: Dict[str, Any] = {}
        self._active_entities: Dict[str, EntityInfo] = {}
        self._scratchpad: List[str] = []

    def add_message(self, message: BaseMessage) -> None:
        self._messages.append(message)
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]

    def add_human_message(self, content: str) -> None:
        self.add_message(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        self.add_message(AIMessage(content=content))

    def get_messages(self) -> List[BaseMessage]:
        return self._messages.copy()

    def set_context(self, key: str, value: Any) -> None:
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        return self._context.get(key, default)

    def track_entity(
        self, name: str, entity_type: str, properties: Dict[str, Any] = None
    ) -> None:
        now = datetime.utcnow()

        if name in self._active_entities:
            entity = self._active_entities[name]
            entity.last_seen = now
            entity.mentions += 1
            if properties:
                entity.properties.update(properties)
        else:
            self._active_entities[name] = EntityInfo(
                name=name,
                entity_type=entity_type,
                properties=properties or {},
                first_seen=now,
                last_seen=now,
            )

    def get_entity(self, name: str) -> Optional[EntityInfo]:
        return self._active_entities.get(name)

    def add_to_scratchpad(self, content: str) -> None:
        self._scratchpad.append(content)

    def get_scratchpad(self) -> str:
        return "\n".join(self._scratchpad)

    def clear_scratchpad(self) -> None:
        self._scratchpad = []

    def to_langchain_memory(self) -> ConversationBufferWindowMemory:
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=self.max_messages,
        )

        for msg in self._messages:
            if isinstance(msg, HumanMessage):
                memory.chat_memory.add_user_message(msg.content)
            elif isinstance(msg, AIMessage):
                memory.chat_memory.add_ai_message(msg.content)

        return memory


class EpisodicMemory:
    CACHE_PREFIX = "episodic_memory"

    def __init__(self, agent_id: str, max_episodes: int = 100):
        self.agent_id = agent_id
        self.max_episodes = max_episodes

    def _get_cache_key(self, episode_id: str) -> str:
        return f"{self.CACHE_PREFIX}:{self.agent_id}:{episode_id}"

    def _get_index_key(self) -> str:
        return f"{self.CACHE_PREFIX}:{self.agent_id}:index"

    async def store_episode(
        self,
        task: str,
        decision: str,
        action: str,
        outcome: str,
        success: bool,
        metadata: Dict[str, Any] = None,
    ) -> str:
        episode_id = hashlib.sha256(
            f"{task}:{decision}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        episode = {
            "id": episode_id,
            "task": task,
            "decision": decision,
            "action": action,
            "outcome": outcome,
            "success": success,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        cache.set(self._get_cache_key(episode_id), episode, timeout=86400 * 30)

        index = cache.get(self._get_index_key()) or []
        index.append(episode_id)
        if len(index) > self.max_episodes:
            old_id = index.pop(0)
            cache.delete(self._get_cache_key(old_id))
        cache.set(self._get_index_key(), index, timeout=86400 * 30)

        return episode_id

    async def retrieve_similar(
        self,
        task: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        index = cache.get(self._get_index_key()) or []
        episodes = []

        task_words = set(task.lower().split())

        for episode_id in index:
            episode = cache.get(self._get_cache_key(episode_id))
            if episode:
                episode_words = set(episode["task"].lower().split())
                similarity = len(task_words & episode_words) / max(
                    len(task_words | episode_words), 1
                )

                if similarity > 0.2:
                    episodes.append((similarity, episode))

        episodes.sort(key=lambda x: x[0], reverse=True)

        return [ep for _, ep in episodes[:limit]]

    async def get_successful_patterns(
        self, task_type: str = None
    ) -> List[Dict[str, Any]]:
        index = cache.get(self._get_index_key()) or []
        successful = []

        for episode_id in index:
            episode = cache.get(self._get_cache_key(episode_id))
            if episode and episode.get("success"):
                if task_type is None or task_type in episode.get("task", ""):
                    successful.append(episode)

        return successful


class SemanticMemory:
    def __init__(
        self,
        collection_name: str = "kubetofu_memory",
        persist_directory: str = "./data/memory",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._vectorstore = None
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is None:
            try:
                from langchain_openai import OpenAIEmbeddings

                self._embeddings = OpenAIEmbeddings(
                    openai_api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY"),
                )
            except Exception:
                from langchain_community.embeddings import HuggingFaceEmbeddings

                self._embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
        return self._embeddings

    def _get_vectorstore(self):
        if self._vectorstore is None:
            embeddings = self._get_embeddings()
            if embeddings:
                self._vectorstore = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=embeddings,
                    persist_directory=self.persist_directory,
                )
        return self._vectorstore

    async def store(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> str:
        from langchain.schema import Document

        vectorstore = self._get_vectorstore()
        if not vectorstore:
            return ""

        doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        doc = Document(
            page_content=content,
            metadata={
                "id": doc_id,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
        )

        vectorstore.add_documents([doc])
        return doc_id

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Dict[str, Any] = None,
    ) -> List[Tuple[str, float]]:
        vectorstore = self._get_vectorstore()
        if not vectorstore:
            return []

        results = vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=filter_metadata,
        )

        return [(doc.page_content, score) for doc, score in results]

    def to_langchain_memory(self, session_id: str) -> VectorStoreRetrieverMemory:
        vectorstore = self._get_vectorstore()
        if not vectorstore:
            return None

        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        return VectorStoreRetrieverMemory(
            retriever=retriever,
            memory_key="relevant_history",
            return_docs=True,
        )


class AgentMemoryManager:
    def __init__(
        self,
        agent_id: str,
        session_id: str,
        llm: Any = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id
        self.llm = llm

        self.working = WorkingMemory(session_id)
        self.episodic = EpisodicMemory(agent_id)
        self.semantic = SemanticMemory(collection_name=f"agent_{agent_id}")

        self._summary_memory = None

    def get_summary_memory(self) -> ConversationSummaryBufferMemory:
        if self._summary_memory is None and self.llm:
            self._summary_memory = ConversationSummaryBufferMemory(
                llm=self.llm,
                max_token_limit=1000,
                memory_key="conversation_summary",
                return_messages=True,
            )
        return self._summary_memory

    def get_combined_memory(self) -> CombinedMemory:
        memories = [self.working.to_langchain_memory()]

        summary = self.get_summary_memory()
        if summary:
            memories.append(summary)

        semantic = self.semantic.to_langchain_memory(self.session_id)
        if semantic:
            memories.append(semantic)

        return CombinedMemory(memories=memories)

    async def add_interaction(
        self,
        human_input: str,
        ai_output: str,
        action_taken: str = None,
        outcome: str = None,
    ) -> None:
        self.working.add_human_message(human_input)
        self.working.add_ai_message(ai_output)

        summary = self.get_summary_memory()
        if summary:
            summary.save_context(
                {"input": human_input},
                {"output": ai_output},
            )

        if len(ai_output) > 100:
            await self.semantic.store(
                f"User: {human_input}\nAssistant: {ai_output}",
                metadata={
                    "type": "interaction",
                    "session_id": self.session_id,
                },
            )

        if action_taken and outcome:
            await self.episodic.store_episode(
                task=human_input,
                decision="Process user request",
                action=action_taken,
                outcome=outcome,
                success="error" not in outcome.lower(),
            )

    async def get_relevant_context(self, query: str, max_items: int = 10) -> str:
        context_parts = []

        messages = self.working.get_messages()[-5:]
        if messages:
            conv_context = "\n".join(
                [
                    f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
                    for m in messages
                ]
            )
            context_parts.append(f"Recent Conversation:\n{conv_context}")

        episodes = await self.episodic.retrieve_similar(query, limit=3)
        if episodes:
            ep_context = "\n".join(
                [
                    f"- Task: {ep['task']}\n  Action: {ep['action']}\n  Outcome: {ep['outcome']}"
                    for ep in episodes
                ]
            )
            context_parts.append(f"Similar Past Tasks:\n{ep_context}")

        semantic_results = await self.semantic.retrieve(query, k=3)
        if semantic_results:
            sem_context = "\n".join([content for content, _ in semantic_results])
            context_parts.append(f"Relevant Knowledge:\n{sem_context}")

        entities = list(self.working._active_entities.values())[:5]
        if entities:
            ent_context = "\n".join(
                [
                    f"- {e.name} ({e.entity_type}): {json.dumps(e.properties)}"
                    for e in entities
                ]
            )
            context_parts.append(f"Active Entities:\n{ent_context}")

        return "\n\n".join(context_parts)
