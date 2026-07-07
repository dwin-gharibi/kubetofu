import os
from typing import Any, Dict, List, Optional
import httpx


class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class APIClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url or os.environ.get(
            "KUBETOFU_API_URL",
            "http://localhost:8000/api/v1",
        )
        self.api_key = api_key or os.environ.get("KUBETOFU_API_KEY")
        self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        response = self.client.request(
            method=method,
            url=endpoint,
            json=data,
            params=params,
        )

        if response.status_code >= 400:
            raise APIError(response.status_code, response.text)

        return response.json()

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        return self._request("POST", endpoint, data=data)

    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        return self._request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> Dict:
        return self._request("DELETE", endpoint)

    def health_check(self) -> Dict:
        return self.get("/health/")

    def list_projects(self) -> List[Dict]:
        return self.get("/projects/")

    def get_project(self, project_id: str) -> Dict:
        return self.get(f"/projects/{project_id}/")

    def create_project(self, name: str, provider: str = "arvancloud") -> Dict:
        return self.post(
            "/projects/",
            data={
                "name": name,
                "provider": provider,
            },
        )

    def chat(self, message: str, session_id: Optional[str] = None) -> Dict:
        return self.post(
            "/chat/",
            data={
                "message": message,
                "session_id": session_id,
            },
        )

    def generate_infrastructure(
        self,
        description: str,
        provider: str = "arvancloud",
    ) -> Dict:
        return self.post(
            "/infrastructure/generate/",
            data={
                "description": description,
                "provider": provider,
            },
        )

    def deploy(
        self,
        configuration: str,
        auto_approve: bool = False,
    ) -> Dict:
        return self.post(
            "/infrastructure/deploy/",
            data={
                "configuration": configuration,
                "auto_approve": auto_approve,
            },
        )
