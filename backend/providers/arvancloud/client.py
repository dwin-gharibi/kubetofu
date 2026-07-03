import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ArvanCloudConfig:
    api_key: str
    region: str = "ir-thr-at1"
    base_url: str = "https://napi.arvancloud.ir"


class ArvanCloudClient:
    REGIONS = {
        "ir-thr-at1": "Tehran - Azadi Tower",
        "ir-thr-mn1": "Tehran - Milad Tower",
        "ir-tbz-at1": "Tabriz",
        "nl-ams-su1": "Amsterdam",
        "de-fra-su1": "Frankfurt",
    }

    ENDPOINTS = {
        "servers": "/ecc/v1/regions/{region}/servers",
        "images": "/ecc/v1/regions/{region}/images",
        "flavors": "/ecc/v1/regions/{region}/sizes",
        "networks": "/ecc/v1/regions/{region}/networks",
        "subnets": "/ecc/v1/regions/{region}/subnets",
        "security_groups": "/ecc/v1/regions/{region}/securities",
        "floating_ips": "/ecc/v1/regions/{region}/floats",
        "volumes": "/ecc/v1/regions/{region}/volumes",
        "snapshots": "/ecc/v1/regions/{region}/snapshots",
        "ssh_keys": "/ecc/v1/regions/{region}/ssh-keys",
    }

    def __init__(self, config: ArvanCloudConfig):
        self.config = config
        self.base_url = config.base_url
        self.region = config.region
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Apikey {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_endpoint(self, resource_type: str) -> str:
        template = self.ENDPOINTS.get(resource_type, "")
        return template.format(region=self.region)

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"ArvanCloud API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.exception(f"ArvanCloud request failed: {e}")
            raise

    async def list_servers(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("servers")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        endpoint = f"{self._get_endpoint('servers')}/{server_id}"
        result = await self._request("GET", endpoint)
        return result.get("data")

    async def create_server(
        self,
        name: str,
        flavor_id: str,
        image_id: str,
        network_ids: List[str] = None,
        ssh_key_ids: List[str] = None,
        security_group_ids: List[str] = None,
        count: int = 1,
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("servers")
        data = {
            "name": name,
            "flavor_id": flavor_id,
            "image_id": image_id,
            "count": count,
        }

        if network_ids:
            data["network_ids"] = network_ids
        if ssh_key_ids:
            data["ssh_key_ids"] = ssh_key_ids
        if security_group_ids:
            data["security_group_ids"] = security_group_ids

        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def delete_server(self, server_id: str) -> bool:
        endpoint = f"{self._get_endpoint('servers')}/{server_id}"
        await self._request("DELETE", endpoint)
        return True

    async def power_on_server(self, server_id: str) -> bool:
        endpoint = f"{self._get_endpoint('servers')}/{server_id}/power-on"
        await self._request("POST", endpoint)
        return True

    async def power_off_server(self, server_id: str) -> bool:
        endpoint = f"{self._get_endpoint('servers')}/{server_id}/power-off"
        await self._request("POST", endpoint)
        return True

    async def reboot_server(self, server_id: str, hard: bool = False) -> bool:
        reboot_type = "hard" if hard else "soft"
        endpoint = f"{self._get_endpoint('servers')}/{server_id}/{reboot_type}-reboot"
        await self._request("POST", endpoint)
        return True

    async def list_images(self, image_type: str = None) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("images")
        params = {}
        if image_type:
            params["type"] = image_type
        result = await self._request("GET", endpoint, params=params)
        return result.get("data", [])

    async def get_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        endpoint = f"{self._get_endpoint('images')}/{image_id}"
        result = await self._request("GET", endpoint)
        return result.get("data")

    async def list_flavors(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("flavors")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def list_networks(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("networks")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def get_network(self, network_id: str) -> Optional[Dict[str, Any]]:
        endpoint = f"{self._get_endpoint('networks')}/{network_id}"
        result = await self._request("GET", endpoint)
        return result.get("data")

    async def create_network(
        self,
        name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("networks")
        data = {
            "name": name,
            "description": description,
        }
        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def delete_network(self, network_id: str) -> bool:
        endpoint = f"{self._get_endpoint('networks')}/{network_id}"
        await self._request("DELETE", endpoint)
        return True

    async def list_subnets(self, network_id: str = None) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("subnets")
        params = {}
        if network_id:
            params["network_id"] = network_id
        result = await self._request("GET", endpoint, params=params)
        return result.get("data", [])

    async def create_subnet(
        self,
        name: str,
        network_id: str,
        cidr: str,
        gateway_ip: str = None,
        enable_dhcp: bool = True,
        dns_nameservers: List[str] = None,
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("subnets")
        data = {
            "name": name,
            "network_id": network_id,
            "cidr": cidr,
            "enable_dhcp": enable_dhcp,
        }
        if gateway_ip:
            data["gateway_ip"] = gateway_ip
        if dns_nameservers:
            data["dns_nameservers"] = dns_nameservers

        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def list_security_groups(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("security_groups")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def create_security_group(
        self,
        name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("security_groups")
        data = {
            "name": name,
            "description": description,
        }
        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def add_security_rule(
        self,
        security_group_id: str,
        direction: str,
        protocol: str,
        port_range_min: int = None,
        port_range_max: int = None,
        remote_ip_prefix: str = "0.0.0.0/0",
    ) -> Dict[str, Any]:
        endpoint = f"{self._get_endpoint('security_groups')}/{security_group_id}/rules"
        data = {
            "direction": direction,
            "protocol": protocol,
            "remote_ip_prefix": remote_ip_prefix,
        }
        if port_range_min:
            data["port_range_min"] = port_range_min
        if port_range_max:
            data["port_range_max"] = port_range_max

        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def list_floating_ips(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("floating_ips")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def create_floating_ip(
        self,
        description: str = "",
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("floating_ips")
        data = {"description": description}
        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def attach_floating_ip(
        self,
        floating_ip_id: str,
        server_id: str,
    ) -> bool:
        endpoint = f"{self._get_endpoint('floating_ips')}/{floating_ip_id}/attach"
        data = {"server_id": server_id}
        await self._request("POST", endpoint, data=data)
        return True

    async def detach_floating_ip(self, floating_ip_id: str) -> bool:
        endpoint = f"{self._get_endpoint('floating_ips')}/{floating_ip_id}/detach"
        await self._request("POST", endpoint)
        return True

    async def list_volumes(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("volumes")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def create_volume(
        self,
        name: str,
        size: int,
        description: str = "",
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("volumes")
        data = {
            "name": name,
            "size": size,
            "description": description,
        }
        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def attach_volume(
        self,
        volume_id: str,
        server_id: str,
    ) -> bool:
        endpoint = f"{self._get_endpoint('volumes')}/{volume_id}/attach"
        data = {"server_id": server_id}
        await self._request("POST", endpoint, data=data)
        return True

    async def detach_volume(self, volume_id: str) -> bool:
        endpoint = f"{self._get_endpoint('volumes')}/{volume_id}/detach"
        await self._request("POST", endpoint)
        return True

    async def list_ssh_keys(self) -> List[Dict[str, Any]]:
        endpoint = self._get_endpoint("ssh_keys")
        result = await self._request("GET", endpoint)
        return result.get("data", [])

    async def create_ssh_key(
        self,
        name: str,
        public_key: str,
    ) -> Dict[str, Any]:
        endpoint = self._get_endpoint("ssh_keys")
        data = {
            "name": name,
            "public_key": public_key,
        }
        result = await self._request("POST", endpoint, data=data)
        return result.get("data")

    async def get_account_info(self) -> Dict[str, Any]:
        endpoint = "/ecc/v1/account"
        result = await self._request("GET", endpoint)
        return result.get("data", {})

    async def get_regions_list(self) -> List[Dict[str, str]]:
        return [{"id": k, "name": v} for k, v in self.REGIONS.items()]
