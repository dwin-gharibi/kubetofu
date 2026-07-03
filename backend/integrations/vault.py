import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class VaultIntegration:
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        self.url = url or os.environ.get("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self.namespace = namespace or os.environ.get("VAULT_NAMESPACE", "")

    def _get_headers(self) -> Dict[str, str]:
        headers = {"X-Vault-Token": self.token}
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        return headers

    async def read_secret(
        self,
        path: str,
        mount: str = "secret",
    ) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/v1/{mount}/data/{path}",
                    headers=self._get_headers(),
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Failed to read secret at {path}: {response.status_code}"
                    )
                    return None

                data = response.json()
                return data.get("data", {}).get("data", {})

        except Exception as e:
            logger.error(f"Vault read error: {e}")
            return None

    async def write_secret(
        self,
        path: str,
        data: Dict[str, Any],
        mount: str = "secret",
    ) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/v1/{mount}/data/{path}",
                    headers=self._get_headers(),
                    json={"data": data},
                    timeout=10.0,
                )

                if response.status_code in [200, 204]:
                    return True

                logger.error(f"Failed to write secret: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Vault write error: {e}")
            return False

    async def delete_secret(
        self,
        path: str,
        mount: str = "secret",
    ) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.url}/v1/{mount}/data/{path}",
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                return response.status_code in [200, 204]

        except Exception as e:
            logger.error(f"Vault delete error: {e}")
            return False

    async def get_database_credentials(
        self,
        role: str,
        mount: str = "database",
    ) -> Optional[Dict[str, str]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/v1/{mount}/creds/{role}",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                return {
                    "username": data["data"]["username"],
                    "password": data["data"]["password"],
                    "lease_id": data["lease_id"],
                    "lease_duration": data["lease_duration"],
                }

        except Exception as e:
            logger.error(f"Failed to get database credentials: {e}")
            return None

    async def get_cloud_credentials(
        self,
        provider: str,
        role: str,
    ) -> Optional[Dict[str, str]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/v1/{provider}/creds/{role}",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                return data.get("data", {})

        except Exception as e:
            logger.error(f"Failed to get cloud credentials: {e}")
            return None

    async def list_secrets(
        self,
        path: str,
        mount: str = "secret",
    ) -> List[str]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    "LIST",
                    f"{self.url}/v1/{mount}/metadata/{path}",
                    headers=self._get_headers(),
                    timeout=10.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                return data.get("data", {}).get("keys", [])

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/v1/sys/health",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
