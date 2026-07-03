from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Resource:
    id: str
    name: str
    type: str
    status: str
    region: str
    properties: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class ProviderConfig:
    api_key: str
    region: str
    project_id: Optional[str] = None
    extra: Dict[str, Any] = None


class BaseProvider(ABC):
    name: str

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def authenticate(self) -> bool:
        pass

    @abstractmethod
    async def list_resources(
        self,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        pass

    @abstractmethod
    async def get_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> Optional[Resource]:
        pass

    @abstractmethod
    async def create_resource(
        self,
        resource_type: str,
        name: str,
        properties: Dict[str, Any],
    ) -> Resource:
        pass

    @abstractmethod
    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        properties: Dict[str, Any],
    ) -> Resource:
        pass

    @abstractmethod
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def get_regions(self) -> List[Dict[str, str]]:
        pass

    @abstractmethod
    async def get_resource_types(self) -> List[str]:
        pass

    @abstractmethod
    def generate_terraform(
        self,
        resources: List[Dict[str, Any]],
    ) -> str:
        pass
