"""VRBO scraper for STR competitive analysis."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from str_researcher.config import RegionConfig
from str_researcher.gathering.base import BaseScraper
from str_researcher.gathering.browser import BrowserManager
from str_researcher.gathering.cache import ScraperCache
from str_researcher.models.comp import STRComp
from str_researcher.utils.geocoding import haversine_distance
from str_researcher.utils.logging import get_logger

logger = get_logger("vrbo")

VRBO_DOMAIN = "vrbo.com"


class VRBOScraper(BaseScraper):
    """Scrapes VRBO listings for competitive analysis."""

    def __init__(self, browser: BrowserManager, cache: ScraperCache):
        self._browser = browser
        self._cache = cache

    def source_name(self) -> str:
        return "vrbo"

    async def scrape(self, config: RegionConfig, **kwargs: Any) -> list[STRComp]:
        """Scrape VRBO listings near the target region."""
        cache_params = {
            "type": "str_comps",
            "region": config.name,
            "lat": config.center_lat,
            "lng": config.center_lng,
        }

        cached = await self._cache.get("vrbo_comps", cache_params)
        if cached:
            logger.info("Using cached VRBO comps (%d)", len(cached))
            return [STRComp(**item) for item in cached]

        comps = await self._scrape_search(config)

        if comps:
            await self._cache.set(
                "vrbo_comps",
                cache_params,
                [c.model_dump(mode="json") for c in comps],
            )

        logger.info("Scraped %d VRBO comps", len(comps))
        return comps

    async def _scrape_search(self, config: RegionConfig) -> list[STRComp]:
        """Scrape VRBO search results."""
        context, page = await self._browser.new_stealth_page()
        comps: list[STRComp] = []

        try:
            url = self._build_search_url(config)
            success = await self._browser.safe_goto(page, url, VRBO_DOMAIN)

            if not success:
                logger.warning("Failed to load VRBO search")
                return []

            await page.wait_for_timeout(5000)

            # Extract from embedded data
            comps = await self._extract_from_state(page, config)

            # Fallback to DOM
            if not comps:
                comps = await self._scrape_from_dom(page, config)

        except Exception as e:
            logger.error("Error scraping VRBO: %s", e)
        finally:
            await context.close()

        return comps

    def _build_search_url(self, config: RegionConfig) -> str:
        """Build a VRBO search URL."""
        lat_offset = config.radius_miles / 69.0
        lng_offset = config.radius_miles / 54.6

        region_query = config.name.replace(" ", "+")
        url = (
            f"https://www.vrbo.com/search?"
            f"destination={region_query}"
            f"&latLong={config.center_lat},{config.center_lng}"
            f"&mapBounds={config.center_lat - lat_offset},"
            f"{config.center_lng - lng_offset},"
            f"{config.center_lat + lat_offset},"
            f"{config.center_lng + lng_offset}"
        )

        if config.min_beds > 1:
            url += f"&minBedrooms={config.min_beds}"

        return url

    async def _extract_from_state(
        self, page: Any, config: RegionConfig
    ) -> list[STRComp]:
        """Extract listing data from VRBO's embedded state."""
        comps = []

        try:
            state_content = await page.evaluate(
                """
                (() => {
                    // VRBO embeds data in __NEXT_DATA__ or similar
                    const nextData = document.getElementById('__NEXT_DATA__');
                    if (nextData) return nextData.textContent;

                    // Also check for dehydrated state
                    const scripts = document.querySelectorAll('script[type="application/json"]');
                    for (const s of scripts) {
                        if (s.textContent && s.textContent.includes('listing') && s.textContent.length > 1000) {
                            return s.textContent;
                        }
                    }
                    return null;
                })()
                """
            )

            if state_content:
                data = json.loads(state_content)
                listings = self._find_listings_in_data(data)
                for listing_data in listings:
                    comp = self._data_to_comp(listing_data, config)
                    if comp:
                        comps.append(comp)

        except Exception as e:
            logger.debug("Failed to extract VRBO state data: %s", e)

        return comps

    async def _scrape_from_dom(
        self, page: Any, config: RegionConfig
    ) -> list[STRComp]:
        """Fallback: scrape VRBO listing data from DOM."""
        comps = []

        try:
            cards = await page.query_selector_all(
                '[data-stid="property-listing"], .HitCollection .Hit'
            )

            for card in cards:
                try:
                    title_el = await card.query_selector(
                        'h3, [data-stid="content-hotel-title"]'
                    )
                    price_el = await card.query_selector(
                        '[data-stid="content-hotel-price"], .price-summary'
                    )
                    link_el = await card.query_selector("a[href*='/vacation-rental/']")
                    rating_el = await card.query_selector(
                        '[data-stid="content-hotel-reviews-rating"]'
                    )
                    review_count_el = await card.query_selector(
                        '[data-stid="content-hotel-reviews-total"]'
                    )

                    if not title_el:
                        continue

                    title = (await title_el.inner_text()).strip()

                    nightly_rate = 0.0
                    if price_el:
                        price_text = (await price_el.inner_text()).strip()
                        price_match = re.search(r"\$?([\d,]+)", price_text)
                        if price_match:
                            nightly_rate = float(
                                price_match.group(1).replace(",", "")
                            )

                    url = ""
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            url = (
                                f"https://www.vrbo.com{href}"
                                if href.startswith("/")
                                else href
                            )

                    review_score = None
                    review_count = 0
                    if rating_el:
                        score_text = (await rating_el.inner_text()).strip()
                        try:
                            review_score = float(score_text)
                        except ValueError:
                            pass
                    if review_count_el:
                        count_text = (await review_count_el.inner_text()).strip()
                        count_match = re.search(r"(\d+)", count_text)
                        if count_match:
                            review_count = int(count_match.group(1))

                    beds = 0
                    bed_match = re.search(r"(\d+)\s*bed", title, re.I)
                    if bed_match:
                        beds = int(bed_match.group(1))

                    if nightly_rate > 0:
                        comp = STRComp(
                            platform="vrbo",
                            listing_url=url,
                            title=title,
                            beds=beds,
                            baths=1.0,
                            accommodates=beds * 2 + 2 if beds else 4,
                            nightly_rate_avg=nightly_rate,
                            review_count=review_count,
                            review_score=review_score,
                        )
                        comps.append(comp)

                except Exception as e:
                    logger.debug("Failed to parse VRBO DOM card: %s", e)

        except Exception as e:
            logger.debug("VRBO DOM scraping failed: %s", e)

        return comps

    @staticmethod
    def _find_listings_in_data(data: dict) -> list[dict]:
        """Find listing objects in VRBO's state data."""
        listings = []

        def _search(obj, depth=0):
            if depth > 15:
                return
            if isinstance(obj, dict):
                if "propertyId" in obj and ("name" in obj or "headline" in obj):
                    listings.append(obj)
                elif "listings" in obj and isinstance(obj["listings"], list):
                    listings.extend(obj["listings"])
                elif "properties" in obj and isinstance(obj["properties"], list):
                    listings.extend(obj["properties"])
                else:
                    for v in obj.values():
                        _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(data)
        return listings

    @staticmethod
    def _data_to_comp(data: dict, config: RegionConfig) -> Optional[STRComp]:
        """Convert VRBO listing data to an STRComp."""
        try:
            name = data.get("name", "") or data.get("headline", "")
            if not name:
                return None

            listing_id = data.get("propertyId", "") or data.get("id", "")

            beds = data.get("bedrooms", 0) or data.get("bedroomCount", 0)
            baths = data.get("bathrooms", 1.0) or data.get("bathroomCount", 1.0)
            accommodates = data.get("sleeps", 0) or data.get("maxOccupancy", beds * 2 + 2)

            # Price
            price_data = data.get("price", {}) or data.get("priceInfo", {})
            nightly_rate = 0.0
            if isinstance(price_data, dict):
                nightly_rate = (
                    price_data.get("lead", {}).get("amount", 0)
                    or price_data.get("pricePerNight", 0)
                    or price_data.get("avgNightly", 0)
                )
            elif isinstance(price_data, (int, float)):
                nightly_rate = float(price_data)

            # Reviews
            reviews = data.get("reviews", {}) or data.get("reviewSummary", {})
            review_score = None
            review_count = 0
            if isinstance(reviews, dict):
                review_score = reviews.get("score") or reviews.get("averageRating")
                review_count = reviews.get("count", 0) or reviews.get("total", 0)

            # Premier Host (VRBO equivalent of Superhost)
            superhost = data.get("isPremierHost", False)

            # Amenities
            amenities = []
            amenity_data = data.get("amenities", [])
            for a in amenity_data:
                if isinstance(a, str):
                    amenities.append(a)
                elif isinstance(a, dict):
                    amenities.append(a.get("name", ""))

            # Location
            geo = data.get("geoCode", {}) or data.get("coordinates", {})
            lat = geo.get("latitude") or data.get("latitude")
            lng = geo.get("longitude") or data.get("longitude")

            distance = 0.0
            if lat and lng:
                distance = haversine_distance(
                    config.center_lat, config.center_lng, float(lat), float(lng)
                )

            url = f"https://www.vrbo.com/vacation-rental/{listing_id}" if listing_id else ""

            annual_revenue = nightly_rate * 365 * 0.60 if nightly_rate else None

            return STRComp(
                platform="vrbo",
                listing_url=url,
                title=name,
                beds=int(beds),
                baths=float(baths),
                accommodates=int(accommodates),
                nightly_rate_avg=float(nightly_rate),
                annual_revenue_est=annual_revenue,
                review_count=int(review_count),
                review_score=float(review_score) if review_score else None,
                superhost=superhost,
                amenities=[a for a in amenities if a],
                distance_miles=distance,
                lat=float(lat) if lat else None,
                lng=float(lng) if lng else None,
            )

        except Exception as e:
            logger.debug("Failed to convert VRBO data to comp: %s", e)
            return None
