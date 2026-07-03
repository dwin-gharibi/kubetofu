import logging
from typing import Any, Dict, List, Optional

from providers.base import BaseProvider, ProviderConfig, Resource
from providers.arvancloud.client import ArvanCloudClient, ArvanCloudConfig
from providers.arvancloud.terraform import ArvanCloudTerraformGenerator

logger = logging.getLogger(__name__)


class ArvanCloudProvider(BaseProvider):
    name = "arvancloud"

    RESOURCE_TYPES = [
        "server",
        "network",
        "subnet",
        "security_group",
        "floating_ip",
        "volume",
        "ssh_key",
    ]

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.arvan_config = ArvanCloudConfig(
            api_key=config.api_key,
            region=config.region,
        )
        self.client = ArvanCloudClient(self.arvan_config)
        self.terraform_generator = ArvanCloudTerraformGenerator()

    async def authenticate(self) -> bool:
        try:
            account = await self.client.get_account_info()
            return bool(account)
        except Exception as e:
            logger.error(f"ArvanCloud authentication failed: {e}")
            return False

    async def list_resources(
        self,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        resources = []

        types_to_list = [resource_type] if resource_type else self.RESOURCE_TYPES

        for rtype in types_to_list:
            try:
                if rtype == "server":
                    items = await self.client.list_servers()
                elif rtype == "network":
                    items = await self.client.list_networks()
                elif rtype == "security_group":
                    items = await self.client.list_security_groups()
                elif rtype == "floating_ip":
                    items = await self.client.list_floating_ips()
                elif rtype == "volume":
                    items = await self.client.list_volumes()
                elif rtype == "ssh_key":
                    items = await self.client.list_ssh_keys()
                else:
                    items = []

                for item in items:
                    resources.append(self._to_resource(rtype, item))
            except Exception as e:
                logger.error(f"Failed to list {rtype}: {e}")

        return resources

    async def get_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> Optional[Resource]:
        try:
            if resource_type == "server":
                item = await self.client.get_server(resource_id)
            elif resource_type == "network":
                item = await self.client.get_network(resource_id)
            else:
                return None

            if item:
                return self._to_resource(resource_type, item)
            return None
        except Exception as e:
            logger.error(f"Failed to get {resource_type}/{resource_id}: {e}")
            return None

    async def create_resource(
        self,
        resource_type: str,
        name: str,
        properties: Dict[str, Any],
    ) -> Resource:
        if resource_type == "server":
            item = await self.client.create_server(
                name=name,
                flavor_id=properties.get("flavor_id"),
                image_id=properties.get("image_id"),
                network_ids=properties.get("network_ids"),
                ssh_key_ids=properties.get("ssh_key_ids"),
                security_group_ids=properties.get("security_group_ids"),
            )
        elif resource_type == "network":
            item = await self.client.create_network(
                name=name,
                description=properties.get("description", ""),
            )
        elif resource_type == "subnet":
            item = await self.client.create_subnet(
                name=name,
                network_id=properties.get("network_id"),
                cidr=properties.get("cidr"),
                gateway_ip=properties.get("gateway_ip"),
                enable_dhcp=properties.get("enable_dhcp", True),
                dns_nameservers=properties.get("dns_nameservers"),
            )
        elif resource_type == "security_group":
            item = await self.client.create_security_group(
                name=name,
                description=properties.get("description", ""),
            )
        elif resource_type == "floating_ip":
            item = await self.client.create_floating_ip(
                description=properties.get("description", ""),
            )
        elif resource_type == "volume":
            item = await self.client.create_volume(
                name=name,
                size=properties.get("size", 10),
                description=properties.get("description", ""),
            )
        elif resource_type == "ssh_key":
            item = await self.client.create_ssh_key(
                name=name,
                public_key=properties.get("public_key"),
            )
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

        return self._to_resource(resource_type, item)

    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        properties: Dict[str, Any],
    ) -> Resource:
        raise NotImplementedError(
            "Resource updates not supported. Please delete and recreate."
        )

    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        if resource_type == "server":
            return await self.client.delete_server(resource_id)
        elif resource_type == "network":
            return await self.client.delete_network(resource_id)
        else:
            raise NotImplementedError(f"Delete not supported for {resource_type}")

    async def get_regions(self) -> List[Dict[str, str]]:
        return await self.client.get_regions_list()

    async def get_resource_types(self) -> List[str]:
        return self.RESOURCE_TYPES

    def generate_terraform(
        self,
        resources: List[Dict[str, Any]],
    ) -> str:
        return self.terraform_generator.generate(
            resources=resources,
            region=self.config.region,
        )

    def _to_resource(
        self,
        resource_type: str,
        item: Dict[str, Any],
    ) -> Resource:
        return Resource(
            id=str(item.get("id", "")),
            name=item.get("name", ""),
            type=resource_type,
            status=item.get("status", "unknown"),
            region=self.config.region,
            properties=item,
            metadata={
                "provider": self.name,
                "created_at": item.get("created_at"),
            },
        )

    async def list_images(self, image_type: str = None) -> List[Dict[str, Any]]:
        return await self.client.list_images(image_type)

    async def list_flavors(self) -> List[Dict[str, Any]]:
        return await self.client.list_flavors()

    async def power_on_server(self, server_id: str) -> bool:
        return await self.client.power_on_server(server_id)

    async def power_off_server(self, server_id: str) -> bool:
        return await self.client.power_off_server(server_id)

    async def attach_floating_ip(
        self,
        floating_ip_id: str,
        server_id: str,
    ) -> bool:
        return await self.client.attach_floating_ip(floating_ip_id, server_id)

    async def attach_volume(
        self,
        volume_id: str,
        server_id: str,
    ) -> bool:
        return await self.client.attach_volume(volume_id, server_id)
