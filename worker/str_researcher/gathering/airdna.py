"""AirDNA API client for STR performance data."""

from __future__ import annotations

from typing import Optional

import httpx

from str_researcher.gathering.cache import ScraperCache
from str_researcher.models.str_performance import (
    MarketMetrics,
    MonthlyProjection,
    STREstimate,
)
from str_researcher.utils.logging import get_logger
from str_researcher.utils.retry import with_retry

logger = get_logger("airdna")

AIRDNA_BASE_URL = "https://api.airdna.co/api/enterprise/v2"


class AirDNAClient:
    """Client for AirDNA's Enterprise API."""

    def __init__(self, api_key: str, cache: ScraperCache):
        self._api_key = api_key
        self._cache = cache
        self._client = httpx.AsyncClient(
            base_url=AIRDNA_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @with_retry(max_attempts=3, retry_on=(httpx.HTTPError,))
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated API request."""
        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def search_market(self, search_term: str) -> Optional[dict]:
        """Search for a market by name. Returns market info with ID."""
        cache_params = {"search_term": search_term}
        cached = await self._cache.get("airdna_market_search", cache_params)
        if cached:
            return cached

        try:
            data = await self._request(
                "GET",
                "/market/search",
                params={"search_term": search_term},
            )
            markets = data.get("markets", [])
            if markets:
                result = markets[0]
                await self._cache.set("airdna_market_search", cache_params, result)
                return result
        except Exception as e:
            logger.error("AirDNA market search failed: %s", e)

        return None

    async def market_metrics(
        self, market_id: str, months: int = 24
    ) -> Optional[MarketMetrics]:
        """Get market-level performance metrics."""
        cache_params = {"market_id": market_id, "months": months}
        cached = await self._cache.get("airdna_market_metrics", cache_params)
        if cached:
            return MarketMetrics(**cached)

        try:
            # Get current metrics
            overview = await self._request(
                "GET",
                f"/market/{market_id}/overview",
            )

            # Get historical data for seasonality
            historical = await self._request(
                "GET",
                f"/market/{market_id}/historical",
                params={"months": months},
            )

            metrics = self._parse_market_metrics(market_id, overview, historical)
            if metrics:
                await self._cache.set(
                    "airdna_market_metrics",
                    cache_params,
                    metrics.model_dump(mode="json"),
                )
            return metrics

        except Exception as e:
            logger.error("AirDNA market metrics failed: %s", e)
            return None

    async def rentalizer_estimate(
        self,
        address: str,
        beds: int,
        baths: float,
        accommodates: int,
    ) -> Optional[STREstimate]:
        """Get a Rentalizer revenue estimate for a specific property."""
        cache_params = {
            "address": address,
            "beds": beds,
            "baths": baths,
            "accommodates": accommodates,
        }
        cached = await self._cache.get("airdna_rentalizer", cache_params)
        if cached:
            return STREstimate(**cached)

        try:
            data = await self._request(
                "POST",
                "/rentalizer/individual",
                json={
                    "address": address,
                    "bedrooms": beds,
                    "bathrooms": baths,
                    "accommodates": accommodates,
                },
            )

            estimate = self._parse_rentalizer_response(address, data)
            if estimate:
                await self._cache.set(
                    "airdna_rentalizer",
                    cache_params,
                    estimate.model_dump(mode="json"),
                )
            return estimate

        except Exception as e:
            logger.error("AirDNA Rentalizer failed for %s: %s", address, e)
            return None

    async def bulk_rentalizer(
        self, properties: list,
    ) -> dict[str, Optional[STREstimate]]:
        """Batch Rentalizer estimates for multiple properties.

        Accepts a list of PropertyListing objects.
        Returns a dict keyed by address.
        """
        results: dict[str, Optional[STREstimate]] = {}
        for prop in properties:
            estimate = await self.rentalizer_estimate(
                address=prop.address,
                beds=prop.beds,
                baths=prop.baths,
                accommodates=prop.accommodates,
            )
            results[prop.address] = estimate
        return results

    async def listings_by_area(
        self,
        lat: float,
        lng: float,
        radius_km: float = 10.0,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Find active STR listings within a radius."""
        cache_params = {"lat": lat, "lng": lng, "radius_km": radius_km}
        cached = await self._cache.get("airdna_listings_area", cache_params)
        if cached:
            return cached

        try:
            params = {
                "latitude": lat,
                "longitude": lng,
                "radius": radius_km,
            }
            if filters:
                params.update(filters)

            data = await self._request(
                "GET",
                "/listing/by-area",
                params=params,
            )

            listings = data.get("listings", [])
            await self._cache.set("airdna_listings_area", cache_params, listings)
            return listings

        except Exception as e:
            logger.error("AirDNA listings by area failed: %s", e)
            return []

    @staticmethod
    def _parse_rentalizer_response(
        address: str, data: dict
    ) -> Optional[STREstimate]:
        """Parse AirDNA Rentalizer API response."""
        try:
            stats = data.get("stats", {})
            revenue = stats.get("revenue", {})
            occupancy = stats.get("occupancy", {})
            adr = stats.get("adr", {})

            annual_revenue = revenue.get("ltm", 0) or revenue.get("annual", 0)
            avg_adr = adr.get("ltm", 0) or adr.get("annual", 0)
            avg_occupancy = occupancy.get("ltm", 0) or occupancy.get("annual", 0)

            # Parse monthly projections
            monthly = []
            monthly_data = data.get("monthly_projections", [])
            for i, m in enumerate(monthly_data[:12], 1):
                monthly.append(
                    MonthlyProjection(
                        month=i,
                        revenue=m.get("revenue", 0),
                        adr=m.get("adr", 0),
                        occupancy_rate=m.get("occupancy", 0),
                    )
                )

            if not annual_revenue:
                return None

            return STREstimate(
                address=address,
                annual_revenue=annual_revenue,
                adr=avg_adr,
                occupancy_rate=avg_occupancy,
                monthly_projections=monthly,
                confidence_score=data.get("confidence_score"),
                source="airdna_rentalizer",
            )

        except Exception as e:
            logger.debug("Failed to parse Rentalizer response: %s", e)
            return None

    @staticmethod
    def _parse_market_metrics(
        market_id: str, overview: dict, historical: dict
    ) -> Optional[MarketMetrics]:
        """Parse AirDNA market overview and historical data."""
        try:
            market_name = overview.get("market_name", "")
            stats = overview.get("stats", {})

            avg_adr = stats.get("adr", {}).get("value", 0)
            avg_occ = stats.get("occupancy", {}).get("value", 0)
            avg_revpar = stats.get("revpar", {}).get("value", 0)
            listing_count = stats.get("active_listings", {}).get("value", 0)
            revenue_growth = stats.get("revenue_growth", {}).get("value")

            # Build seasonality index from historical monthly data
            seasonality = {}
            monthly_data = historical.get("monthly", [])
            if monthly_data:
                revenues = [m.get("revenue", 0) for m in monthly_data[-12:]]
                if revenues:
                    avg_monthly = sum(revenues) / len(revenues)
                    if avg_monthly > 0:
                        for i, rev in enumerate(revenues):
                            month = (i % 12) + 1
                            seasonality[month] = rev / avg_monthly

            return MarketMetrics(
                market_id=market_id,
                market_name=market_name,
                adr=avg_adr,
                occupancy_rate=avg_occ,
                revpar=avg_revpar,
                active_listing_count=listing_count,
                revenue_growth_yoy=revenue_growth,
                seasonality_index=seasonality,
            )

        except Exception as e:
            logger.debug("Failed to parse market metrics: %s", e)
            return None
