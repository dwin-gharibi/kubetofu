import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    name: str = "arvancloud"
    region: str = "ir-thr-at1"
    api_key: Optional[str] = None


class AgentConfig(BaseModel):
    enabled: bool = True
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.1
    max_iterations: int = 10


class AgentsConfig(BaseModel):
    planner: AgentConfig = Field(default_factory=AgentConfig)
    security: AgentConfig = Field(default_factory=AgentConfig)
    cost: AgentConfig = Field(default_factory=AgentConfig)
    deployment: AgentConfig = Field(default_factory=AgentConfig)
    monitoring: AgentConfig = Field(default_factory=AgentConfig)


class KubeTofuConfig(BaseModel):
    project_name: str = "my-project"
    version: str = "1.0.0"
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    terraform_version: str = ">= 1.6.0"
    auto_approve: bool = False


def get_config_path() -> Path:
    local_config = Path.cwd() / "kubetofu.yaml"
    if local_config.exists():
        return local_config

    global_config = Path.home() / ".config" / "kubetofu" / "config.yaml"
    if global_config.exists():
        return global_config

    return local_config


def get_config() -> KubeTofuConfig:
    config_path = get_config_path()

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
            return KubeTofuConfig(**data) if data else KubeTofuConfig()

    return KubeTofuConfig()


def save_config(config: KubeTofuConfig, path: Optional[Path] = None) -> None:
    path = path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False)


def get_env_value(key: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(key)
    if value:
        return value

    value = os.environ.get(key.upper())
    if value:
        return value

    return default
