import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class Price:
    resource_type: str
    resource_id: str
    provider: str
    region: str
    unit_price: float
    currency: str
    unit: str
    effective_date: datetime
    metadata: Dict[str, Any] = None

    @property
    def monthly_price(self) -> float:
        if self.unit == "hour":
            return self.unit_price * 730
        elif self.unit == "month":
            return self.unit_price
        elif self.unit == "day":
            return self.unit_price * 30
        return self.unit_price


@dataclass
class CostEstimate:
    resources: List[Dict[str, Any]]
    monthly_total: float
    annual_total: float
    currency: str
    provider: str
    timestamp: datetime
    breakdown: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resources": self.resources,
            "monthly_total": self.monthly_total,
            "annual_total": self.annual_total,
            "currency": self.currency,
            "provider": self.provider,
            "timestamp": self.timestamp.isoformat(),
            "breakdown": self.breakdown,
        }


class ProviderPricingAPI:
    provider: str = "base"

    async def fetch_prices(self, region: str) -> Dict[str, Price]:
        raise NotImplementedError

    async def get_price(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        region: str,
    ) -> Optional[Price]:
        raise NotImplementedError


class ArvanCloudPricingAPI(ProviderPricingAPI):
    provider = "arvancloud"
    BASE_URL = "https://napi.arvancloud.ir"
    CACHE_TTL = 3600

    def __init__(self):
        self.api_key = settings.ARVANCLOUD_SETTINGS.get("API_KEY", "")

    async def fetch_prices(self, region: str) -> Dict[str, Price]:
        prices = {}

        flavors = await self._fetch_flavors(region)
        for flavor in flavors:
            price = Price(
                resource_type="compute",
                resource_id=flavor.get("id", ""),
                provider=self.provider,
                region=region,
                unit_price=float(flavor.get("price_per_hour", 0)),
                currency="IRR",
                unit="hour",
                effective_date=datetime.utcnow(),
                metadata={
                    "vcpus": flavor.get("vcpus"),
                    "ram_mb": flavor.get("ram"),
                    "disk_gb": flavor.get("disk"),
                },
            )
            prices[f"compute:{flavor.get('id')}"] = price

        volume_prices = await self._fetch_volume_pricing(region)
        prices.update(volume_prices)

        return prices

    async def _fetch_flavors(self, region: str) -> List[Dict]:
        url = f"{self.BASE_URL}/ecc/v1/regions/{region}/sizes"

        headers = {
            "Authorization": f"Apikey {self.api_key}",
            "Content-Type": "application/json",
        }

        cache_key = f"arvancloud:flavors:{region}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    flavors = data.get("data", [])
                    cache.set(cache_key, flavors, self.CACHE_TTL)
                    return flavors
                else:
                    logger.warning(f"ArvanCloud API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch ArvanCloud flavors: {e}")
            return []

    async def _fetch_volume_pricing(self, region: str) -> Dict[str, Price]:
        return {
            "volume:ssd": Price(
                resource_type="volume",
                resource_id="ssd",
                provider=self.provider,
                region=region,
                unit_price=2000,
                currency="IRR",
                unit="GB/month",
                effective_date=datetime.utcnow(),
            ),
            "volume:hdd": Price(
                resource_type="volume",
                resource_id="hdd",
                provider=self.provider,
                region=region,
                unit_price=1000,
                currency="IRR",
                unit="GB/month",
                effective_date=datetime.utcnow(),
            ),
        }

    async def get_price(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        region: str,
    ) -> Optional[Price]:
        prices = await self.fetch_prices(region)

        if resource_type == "compute":
            flavor_id = resource_spec.get("flavor_id", "")
            return prices.get(f"compute:{flavor_id}")

        elif resource_type == "volume":
            volume_type = resource_spec.get("type", "ssd")
            return prices.get(f"volume:{volume_type}")

        return None


class DynamicPricingService:
    def __init__(self):
        self.providers: Dict[str, ProviderPricingAPI] = {
            "arvancloud": ArvanCloudPricingAPI(),
        }

    async def get_prices(
        self,
        provider: str,
        region: str,
    ) -> Dict[str, Price]:
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")

        return await self.providers[provider].fetch_prices(region)

    async def estimate_cost(
        self,
        resources: List[Dict[str, Any]],
        provider: str = "arvancloud",
        region: str = "ir-thr-at1",
        duration_months: int = 1,
    ) -> CostEstimate:
        pricing_api = self.providers.get(provider)
        if not pricing_api:
            raise ValueError(f"Unknown provider: {provider}")

        prices = await pricing_api.fetch_prices(region)

        resource_costs = []
        breakdown = {
            "compute": 0,
            "storage": 0,
            "network": 0,
            "other": 0,
        }

        for resource in resources:
            resource_type = resource.get("type", "")
            name = resource.get("name", "unknown")
            count = resource.get("count", 1)

            if resource_type in ["server", "compute", "abrak"]:
                flavor_id = resource.get("flavor_id", "g2-2-2-0")
                price = prices.get(f"compute:{flavor_id}")

                if price:
                    monthly = price.monthly_price * count
                    breakdown["compute"] += monthly
                    resource_costs.append(
                        {
                            "name": name,
                            "type": "compute",
                            "flavor": flavor_id,
                            "count": count,
                            "monthly_cost": monthly,
                        }
                    )

            elif resource_type == "volume":
                size_gb = resource.get("size", 10)
                volume_type = resource.get("volume_type", "ssd")
                price = prices.get(f"volume:{volume_type}")

                if price:
                    monthly = price.unit_price * size_gb * count
                    breakdown["storage"] += monthly
                    resource_costs.append(
                        {
                            "name": name,
                            "type": "storage",
                            "size_gb": size_gb,
                            "count": count,
                            "monthly_cost": monthly,
                        }
                    )

            elif resource_type == "floating_ip":
                monthly = 50000 * count
                breakdown["network"] += monthly
                resource_costs.append(
                    {
                        "name": name,
                        "type": "network",
                        "count": count,
                        "monthly_cost": monthly,
                    }
                )

        monthly_total = sum(breakdown.values())
        annual_total = monthly_total * 12

        return CostEstimate(
            resources=resource_costs,
            monthly_total=monthly_total * duration_months,
            annual_total=annual_total,
            currency="IRR" if provider == "arvancloud" else "USD",
            provider=provider,
            timestamp=datetime.utcnow(),
            breakdown=breakdown,
        )

    async def compare_providers(
        self,
        resources: List[Dict[str, Any]],
        providers: List[str] = None,
    ) -> Dict[str, CostEstimate]:
        providers = providers or list(self.providers.keys())

        estimates = {}
        for provider in providers:
            try:
                estimate = await self.estimate_cost(resources, provider)
                estimates[provider] = estimate
            except Exception as e:
                logger.error(f"Failed to estimate for {provider}: {e}")

        return estimates


pricing_service = DynamicPricingService()
