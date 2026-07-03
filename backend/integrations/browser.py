import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class WebPage:
    url: str
    title: str
    content: str
    links: List[str]
    code_blocks: List[Dict[str, str]]


class BrowserIntegration:
    ALLOWED_DOMAINS = [
        "terraform.io",
        "registry.terraform.io",
        "kubernetes.io",
        "docs.arvancloud.ir",
        "arvancloud.ir",
        "github.com",
        "stackoverflow.com",
        "docs.aws.amazon.com",
        "cloud.google.com",
        "learn.microsoft.com",
        "medium.com",
        "dev.to",
    ]

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self._last_request = 0.0

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        return any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in self.ALLOWED_DOMAINS
        )

    async def _rate_limit(self):
        import time

        now = time.time()
        elapsed = now - self._last_request

        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)

        self._last_request = time.time()

    async def fetch(self, url: str) -> Optional[WebPage]:
        if not self._is_allowed(url):
            logger.warning(f"URL not in allowed domains: {url}")
            return None

        await self._rate_limit()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Kube-Tofu-Agent/1.0 (Infrastructure Research)",
                    },
                    follow_redirects=True,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return None

                return self._parse_html(url, response.text)

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def _parse_html(self, url: str, html: str) -> WebPage:
        soup = BeautifulSoup(html, "html.parser")

        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        title = soup.title.string if soup.title else ""

        main = soup.find("main") or soup.find("article") or soup.body
        content = main.get_text(separator="\n", strip=True) if main else ""

        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content[:10000]

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = urljoin(url, href)
            if href.startswith("http"):
                links.append(href)

        code_blocks = []
        for code in soup.find_all(["pre", "code"]):
            code_text = code.get_text(strip=True)
            if len(code_text) > 10:
                language = ""
                classes = code.get("class", [])
                for cls in classes:
                    if cls.startswith("language-"):
                        language = cls.replace("language-", "")
                        break
                    elif cls in ["hcl", "terraform", "yaml", "json", "bash", "python"]:
                        language = cls
                        break

                code_blocks.append(
                    {
                        "language": language,
                        "content": code_text[:2000],
                    }
                )

        return WebPage(
            url=url,
            title=title,
            content=content,
            links=links[:50],
            code_blocks=code_blocks[:10],
        )

    async def search_documentation(
        self,
        query: str,
        site: str = "terraform.io",
    ) -> List[WebPage]:
        pages = []

        if "terraform" in site:
            provider_match = re.search(r"(arvancloud|aws|google|azure)", query.lower())
            if provider_match:
                provider = provider_match.group(1)
                url = f"https://registry.terraform.io/providers/{provider}/latest/docs"
                page = await self.fetch(url)
                if page:
                    pages.append(page)

        elif "kubernetes" in site:
            url = f"https://kubernetes.io/docs/search/?q={query}"
            page = await self.fetch(url)
            if page:
                pages.append(page)

        return pages

    async def get_terraform_resource_docs(
        self,
        provider: str,
        resource: str,
    ) -> Optional[WebPage]:
        url = f"https://registry.terraform.io/providers/{provider}/latest/docs/resources/{resource}"
        return await self.fetch(url)

    async def get_kubernetes_docs(
        self,
        resource: str,
    ) -> Optional[WebPage]:
        url = f"https://kubernetes.io/docs/concepts/workloads/controllers/{resource}/"
        return await self.fetch(url)
