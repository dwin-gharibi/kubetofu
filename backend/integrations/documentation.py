import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class Document:
    id: str
    content: str
    source: str
    source_type: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    document: Document
    score: float


class DocumentationRAG:
    def __init__(self, vector_store_path: Optional[str] = None):
        self.vector_store_path = vector_store_path or "./data/vectors"
        self._vector_store = None
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is None:
            try:
                from langchain_openai import OpenAIEmbeddings

                self._embeddings = OpenAIEmbeddings(
                    openai_api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY"),
                )
            except Exception as e:
                logger.warning(f"Failed to load OpenAI embeddings: {e}")
                try:
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                    self._embeddings = HuggingFaceEmbeddings(
                        model_name="sentence-transformers/all-MiniLM-L6-v2"
                    )
                except Exception as e2:
                    logger.error(f"Failed to load any embeddings: {e2}")

        return self._embeddings

    def _get_vector_store(self):
        if self._vector_store is None:
            try:
                from langchain_community.vectorstores import Chroma

                embeddings = self._get_embeddings()
                if embeddings:
                    self._vector_store = Chroma(
                        persist_directory=self.vector_store_path,
                        embedding_function=embeddings,
                        collection_name="kubetofu_docs",
                    )
            except Exception as e:
                logger.error(f"Failed to initialize vector store: {e}")

        return self._vector_store

    async def add_documents(
        self,
        documents: List[Document],
    ) -> bool:
        vector_store = self._get_vector_store()
        if not vector_store:
            return False

        try:
            from langchain.schema import Document as LCDocument

            lc_docs = [
                LCDocument(
                    page_content=doc.content,
                    metadata={
                        "id": doc.id,
                        "source": doc.source,
                        "source_type": doc.source_type,
                        **doc.metadata,
                    },
                )
                for doc in documents
            ]

            vector_store.add_documents(lc_docs)
            return True

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False

    async def search(
        self,
        query: str,
        k: int = 5,
        source_type: Optional[str] = None,
    ) -> List[SearchResult]:
        vector_store = self._get_vector_store()
        if not vector_store:
            return []

        try:
            filter_dict = {}
            if source_type:
                filter_dict["source_type"] = source_type

            results = vector_store.similarity_search_with_score(
                query,
                k=k,
                filter=filter_dict if filter_dict else None,
            )

            search_results = []
            for doc, score in results:
                document = Document(
                    id=doc.metadata.get("id", ""),
                    content=doc.page_content,
                    source=doc.metadata.get("source", ""),
                    source_type=doc.metadata.get("source_type", ""),
                    metadata=doc.metadata,
                )
                search_results.append(SearchResult(document=document, score=score))

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        results = await self.search(query, k=5)

        context_parts = []
        total_length = 0

        for result in results:
            content = result.document.content
            source = result.document.source

            content_tokens = len(content.split()) * 1.3

            if total_length + content_tokens > max_tokens:
                remaining = max_tokens - total_length
                words = content.split()[: int(remaining / 1.3)]
                content = " ".join(words)

            context_parts.append(f"Source: {source}\n{content}\n---")
            total_length += content_tokens

            if total_length >= max_tokens:
                break

        return "\n".join(context_parts)

    async def index_terraform_docs(
        self,
        provider: str = "arvancloud",
    ) -> int:
        from integrations.browser import BrowserIntegration

        browser = BrowserIntegration()
        indexed = 0

        resources = [
            "abrak",
            "network",
            "subnet",
            "security_group",
            "volume",
            "floating_ip",
        ]

        documents = []

        for resource in resources:
            page = await browser.get_terraform_resource_docs(provider, resource)
            if page:
                doc = Document(
                    id=f"terraform:{provider}:{resource}",
                    content=page.content,
                    source=page.url,
                    source_type="terraform",
                    metadata={
                        "provider": provider,
                        "resource": resource,
                        "title": page.title,
                    },
                )
                documents.append(doc)
                indexed += 1

        if documents:
            await self.add_documents(documents)

        return indexed

    async def index_kubernetes_docs(self) -> int:
        from integrations.browser import BrowserIntegration

        browser = BrowserIntegration()
        indexed = 0

        resources = [
            "deployment",
            "statefulset",
            "daemonset",
            "service",
            "ingress",
        ]

        documents = []

        for resource in resources:
            page = await browser.get_kubernetes_docs(resource)
            if page:
                doc = Document(
                    id=f"kubernetes:{resource}",
                    content=page.content,
                    source=page.url,
                    source_type="kubernetes",
                    metadata={
                        "resource": resource,
                        "title": page.title,
                    },
                )
                documents.append(doc)
                indexed += 1

        if documents:
            await self.add_documents(documents)

        return indexed
