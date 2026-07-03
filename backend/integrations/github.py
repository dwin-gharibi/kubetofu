import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Repository:
    name: str
    full_name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    topics: List[str]
    default_branch: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    labels: List[str]
    author: str
    created_at: datetime
    url: str


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    state: str
    head_branch: str
    base_branch: str
    author: str
    created_at: datetime
    url: str
    merged: bool


class GitHubIntegration:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Kube-Tofu-Agent",
            }
            if self.token:
                headers["Authorization"] = f"token {self.token}"

            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_repositories(
        self,
        query: str,
        language: Optional[str] = None,
        sort: str = "stars",
        limit: int = 10,
    ) -> List[Repository]:
        search_query = query
        if language:
            search_query += f" language:{language}"

        response = await self.client.get(
            "/search/repositories",
            params={
                "q": search_query,
                "sort": sort,
                "per_page": limit,
            },
        )

        if response.status_code != 200:
            logger.error(f"GitHub search failed: {response.status_code}")
            return []

        data = response.json()
        repositories = []

        for item in data.get("items", []):
            repo = Repository(
                name=item["name"],
                full_name=item["full_name"],
                description=item.get("description") or "",
                url=item["html_url"],
                stars=item["stargazers_count"],
                forks=item["forks_count"],
                language=item.get("language") or "",
                topics=item.get("topics") or [],
                default_branch=item.get("default_branch", "main"),
                created_at=datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    item["updated_at"].replace("Z", "+00:00")
                ),
            )
            repositories.append(repo)

        return repositories

    async def search_terraform_modules(
        self,
        provider: str = "arvancloud",
        resource_type: Optional[str] = None,
    ) -> List[Repository]:
        query = f"terraform {provider}"
        if resource_type:
            query += f" {resource_type}"

        return await self.search_repositories(
            query=query,
            language="HCL",
            sort="stars",
            limit=10,
        )

    async def search_code(
        self,
        query: str,
        extension: Optional[str] = None,
        repo: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        search_query = query
        if extension:
            search_query += f" extension:{extension}"
        if repo:
            search_query += f" repo:{repo}"

        response = await self.client.get(
            "/search/code",
            params={
                "q": search_query,
                "per_page": limit,
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for item in data.get("items", []):
            results.append(
                {
                    "name": item["name"],
                    "path": item["path"],
                    "repository": item["repository"]["full_name"],
                    "url": item["html_url"],
                    "sha": item["sha"],
                }
            )

        return results

    async def search_issues(
        self,
        query: str,
        state: str = "all",
        labels: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Issue]:
        search_query = f"{query} is:issue"
        if state != "all":
            search_query += f" state:{state}"
        if labels:
            for label in labels:
                search_query += f" label:{label}"

        response = await self.client.get(
            "/search/issues",
            params={
                "q": search_query,
                "per_page": limit,
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        issues = []

        for item in data.get("items", []):
            issue = Issue(
                number=item["number"],
                title=item["title"],
                body=item.get("body") or "",
                state=item["state"],
                labels=[l["name"] for l in item.get("labels", [])],
                author=item["user"]["login"],
                created_at=datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                ),
                url=item["html_url"],
            )
            issues.append(issue)

        return issues

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> Optional[str]:
        url = f"/repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref

        response = await self.client.get(url, params=params)

        if response.status_code != 200:
            return None

        data = response.json()

        if data.get("encoding") == "base64":
            import base64

            return base64.b64decode(data["content"]).decode("utf-8")

        return data.get("content")

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Optional[Issue]:
        response = await self.client.post(
            f"/repos/{owner}/{repo}/issues",
            json={
                "title": title,
                "body": body,
                "labels": labels or [],
            },
        )

        if response.status_code != 201:
            logger.error(f"Failed to create issue: {response.status_code}")
            return None

        data = response.json()

        return Issue(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            state=data["state"],
            labels=[l["name"] for l in data.get("labels", [])],
            author=data["user"]["login"],
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            url=data["html_url"],
        )

    async def get_terraform_module_readme(
        self,
        owner: str,
        repo: str,
    ) -> Optional[str]:
        for filename in ["README.md", "readme.md", "README.MD"]:
            content = await self.get_file_content(owner, repo, filename)
            if content:
                return content
        return None
