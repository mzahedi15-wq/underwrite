"""Zillow scraper for property listings."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from str_researcher.config import RegionConfig
from str_researcher.gathering.base import BaseScraper
from str_researcher.gathering.browser import BrowserManager
from str_researcher.gathering.cache import ScraperCache
from str_researcher.models.property import PropertyListing
from str_researcher.utils.logging import get_logger

logger = get_logger("zillow")

ZILLOW_DOMAIN = "zillow.com"


class ZillowScraper(BaseScraper):
    """Scrapes property listings from Zillow."""

    def __init__(self, browser: BrowserManager, cache: ScraperCache):
        self._browser = browser
        self._cache = cache

    def source_name(self) -> str:
        return "zillow"

    async def scrape(self, config: RegionConfig, **kwargs: Any) -> list[PropertyListing]:
        """Scrape active listings from Zillow."""
        cache_params = {
            "type": "listings",
            "region": config.name,
            "min_price": config.min_price,
            "max_price": config.max_price,
            "min_beds": config.min_beds,
        }

        cached = await self._cache.get("zillow_listings", cache_params)
        if cached:
            logger.info("Using cached Zillow listings (%d)", len(cached))
            return [PropertyListing(**item) for item in cached]

        listings = []

        if config.zillow_search_url:
            listings = await self._scrape_from_url(config.zillow_search_url, config)
        else:
            listings = await self._scrape_from_search(config)

        if listings:
            await self._cache.set(
                "zillow_listings",
                cache_params,
                [l.model_dump(mode="json") for l in listings],
            )

        logger.info("Scraped %d listings from Zillow", len(listings))
        return listings

    async def _scrape_from_url(
        self, url: str, config: RegionConfig
    ) -> list[PropertyListing]:
        """Scrape from a user-provided Zillow search URL."""
        context, page = await self._browser.new_stealth_page()
        listings = []

        try:
            success = await self._browser.safe_goto(page, url, ZILLOW_DOMAIN)
            if not success:
                logger.warning("Failed to load Zillow URL")
                return []

            # Wait for content to load
            await page.wait_for_timeout(3000)

            # Primary strategy: extract __NEXT_DATA__ JSON
            listings = await self._extract_from_next_data(page, config)

            # Fallback: try gdpClientCache
            if not listings:
                listings = await self._extract_from_gdp_cache(page, config)

            # Final fallback: DOM scraping
            if not listings:
                listings = await self._scrape_from_dom(page, config)

        except Exception as e:
            logger.error("Error scraping Zillow: %s", e)
        finally:
            await context.close()

        return listings

    async def _scrape_from_search(self, config: RegionConfig) -> list[PropertyListing]:
        """Build and scrape a Zillow search URL from region config.

        Tries multiple URL patterns since Zillow's URL structure varies by region type.
        Note: Zillow aggressively blocks headless browsers. If all patterns return 403,
        the pipeline will rely on Redfin data instead.
        """
        name = config.name.strip()

        # Build candidate URLs in order of likelihood
        candidates = []

        # Try with state suffix variations (e.g., "mariposa-county-ca")
        parts = [p.strip() for p in name.split(",")]
        if len(parts) >= 2:
            city_slug = parts[0].lower().replace(" ", "-")
            state_slug = parts[1].strip().lower().replace(" ", "-")
            candidates.append(f"https://www.zillow.com/{city_slug}-{state_slug}/")
            candidates.append(f"https://www.zillow.com/homes/{parts[0].replace(' ', '-')},-{parts[1].strip()}_rb/")
        else:
            slug = name.lower().replace(" ", "-").replace(",", "")
            candidates.append(f"https://www.zillow.com/{slug}/")
            candidates.append(f"https://www.zillow.com/homes/{name.replace(' ', '-')}_rb/")

        for url in candidates:
            listings = await self._scrape_from_url(url, config)
            if listings:
                return listings

        logger.warning(
            "Zillow blocked all URL patterns for '%s'. "
            "This is expected without a residential proxy. "
            "Redfin data will be used instead.",
            name,
        )
        return []

    async def _extract_from_next_data(
        self, page: Any, config: RegionConfig
    ) -> list[PropertyListing]:
        """Extract listing data from Zillow's __NEXT_DATA__ script tag."""
        listings = []

        json_data = await self._browser.extract_json_from_script(page, "__NEXT_DATA__")
        if not json_data:
            return []

        try:
            # Navigate through __NEXT_DATA__ to find search results
            results = self._find_search_results(json_data)
            for result in results:
                listing = self._result_to_listing(result)
                if listing and self._matches_filters(listing, config):
                    listings.append(listing)
        except Exception as e:
            logger.debug("Error parsing __NEXT_DATA__: %s", e)

        return listings

    async def _extract_from_gdp_cache(
        self, page: Any, config: RegionConfig
    ) -> list[PropertyListing]:
        """Extract from Zillow's gdpClientCache in page scripts."""
        listings = []

        try:
            scripts = await page.evaluate(
                """
                (() => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        if (s.textContent && s.textContent.includes('gdpClientCache')) {
                            return s.textContent;
                        }
                    }
                    return null;
                })()
                """
            )

            if scripts:
                # Extract JSON from the script content
                match = re.search(r'"gdpClientCache"\s*:\s*({.*?})\s*[,}]', scripts)
                if match:
                    cache_data = json.loads(match.group(1))
                    for key, value in cache_data.items():
                        if isinstance(value, str):
                            try:
                                data = json.loads(value)
                                if isinstance(data, dict) and "property" in data:
                                    listing = self._property_data_to_listing(
                                        data["property"]
                                    )
                                    if listing and self._matches_filters(listing, config):
                                        listings.append(listing)
                            except json.JSONDecodeError:
                                pass

        except Exception as e:
            logger.debug("Error extracting gdpClientCache: %s", e)

        return listings

    async def _scrape_from_dom(
        self, page: Any, config: RegionConfig
    ) -> list[PropertyListing]:
        """Fallback: scrape listing data from Zillow DOM elements."""
        listings = []

        try:
            cards = await page.query_selector_all(
                'article[data-test="property-card"], .list-card'
            )

            for card in cards:
                try:
                    price_el = await card.query_selector(
                        '[data-test="property-card-price"], .list-card-price'
                    )
                    addr_el = await card.query_selector(
                        '[data-test="property-card-addr"], address'
                    )
                    link_el = await card.query_selector(
                        'a[data-test="property-card-link"], a.list-card-link'
                    )
                    details_el = await card.query_selector(
                        '[data-test="property-card-details"], .list-card-details'
                    )

                    if not (price_el and addr_el):
                        continue

                    price_text = (await price_el.inner_text()).strip()
                    price = int(re.sub(r"[^\d]", "", price_text))

                    addr_text = (await addr_el.inner_text()).strip()
                    parts = addr_text.split(",")
                    street = parts[0].strip()
                    city = parts[1].strip() if len(parts) > 1 else ""
                    state_zip = parts[2].strip() if len(parts) > 2 else ""
                    state_parts = state_zip.split()
                    state = state_parts[0] if state_parts else ""
                    zip_code = state_parts[1] if len(state_parts) > 1 else ""

                    url = ""
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            url = (
                                f"https://www.zillow.com{href}"
                                if href.startswith("/")
                                else href
                            )

                    beds, baths, sqft = 0, 0.0, None
                    if details_el:
                        details_text = await details_el.inner_text()
                        bed_match = re.search(r"(\d+)\s*bd", details_text, re.I)
                        bath_match = re.search(r"([\d.]+)\s*ba", details_text, re.I)
                        sqft_match = re.search(
                            r"([\d,]+)\s*sqft", details_text, re.I
                        )
                        if bed_match:
                            beds = int(bed_match.group(1))
                        if bath_match:
                            baths = float(bath_match.group(1))
                        if sqft_match:
                            sqft = int(sqft_match.group(1).replace(",", ""))

                    listing = PropertyListing(
                        source="zillow",
                        source_url=url,
                        address=street,
                        city=city,
                        state=state,
                        zip_code=zip_code,
                        list_price=price,
                        beds=beds,
                        baths=baths,
                        sqft=sqft,
                    )

                    if self._matches_filters(listing, config):
                        listings.append(listing)

                except Exception as e:
                    logger.debug("Failed to parse Zillow DOM card: %s", e)

        except Exception as e:
            logger.debug("Zillow DOM scraping failed: %s", e)

        return listings

    @staticmethod
    def _find_search_results(next_data: dict) -> list[dict]:
        """Recursively find search result objects in __NEXT_DATA__."""
        results = []

        def _search(obj, depth=0):
            if depth > 15:
                return
            if isinstance(obj, dict):
                # Look for search result patterns
                if "zpid" in obj:
                    results.append(obj)
                elif "searchResults" in obj:
                    sr = obj["searchResults"]
                    if isinstance(sr, dict) and "listResults" in sr:
                        results.extend(sr["listResults"])
                    elif isinstance(sr, list):
                        results.extend(sr)
                else:
                    for v in obj.values():
                        _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(next_data)
        return results

    @staticmethod
    def _result_to_listing(result: dict) -> Optional[PropertyListing]:
        """Convert a Zillow search result to a PropertyListing."""
        try:
            price = result.get("price") or result.get("unformattedPrice")
            if isinstance(price, str):
                price = int(re.sub(r"[^\d]", "", price))
            if not price:
                return None

            address = result.get("address", "")
            if isinstance(address, dict):
                street = address.get("streetAddress", "")
                city = address.get("city", "")
                state = address.get("state", "")
                zip_code = address.get("zipcode", "")
            else:
                parts = str(address).split(",")
                street = parts[0].strip() if parts else ""
                city = parts[1].strip() if len(parts) > 1 else ""
                state_zip = parts[2].strip() if len(parts) > 2 else ""
                sp = state_zip.split()
                state = sp[0] if sp else ""
                zip_code = sp[1] if len(sp) > 1 else ""

            if not street:
                return None

            beds = result.get("beds") or result.get("bedrooms", 0)
            baths = result.get("baths") or result.get("bathrooms", 0)
            sqft = result.get("area") or result.get("livingArea")

            lat = result.get("latLong", {}).get("latitude") or result.get("latitude")
            lng = result.get("latLong", {}).get("longitude") or result.get("longitude")

            url = result.get("detailUrl", "") or result.get("hdpUrl", "")
            if url and not url.startswith("http"):
                url = f"https://www.zillow.com{url}"

            return PropertyListing(
                source="zillow",
                source_url=url,
                address=street,
                city=city,
                state=state,
                zip_code=str(zip_code),
                lat=lat,
                lng=lng,
                list_price=int(price),
                beds=int(beds) if beds else 0,
                baths=float(baths) if baths else 0.0,
                sqft=int(sqft) if sqft else None,
            )

        except Exception:
            return None

    @staticmethod
    def _property_data_to_listing(prop: dict) -> Optional[PropertyListing]:
        """Convert a Zillow property data object to a PropertyListing."""
        try:
            return PropertyListing(
                source="zillow",
                source_url=prop.get("url", ""),
                address=prop.get("streetAddress", ""),
                city=prop.get("city", ""),
                state=prop.get("state", ""),
                zip_code=str(prop.get("zipcode", "")),
                lat=prop.get("latitude"),
                lng=prop.get("longitude"),
                list_price=int(prop.get("price", 0)),
                beds=int(prop.get("bedrooms", 0)),
                baths=float(prop.get("bathrooms", 0)),
                sqft=int(prop.get("livingArea")) if prop.get("livingArea") else None,
                year_built=prop.get("yearBuilt"),
                description=prop.get("description"),
            )
        except Exception:
            return None

    @staticmethod
    def _matches_filters(listing: PropertyListing, config: RegionConfig) -> bool:
        if listing.list_price < config.min_price or listing.list_price > config.max_price:
            return False
        if listing.beds < config.min_beds or listing.beds > config.max_beds:
            return False
        return True

    async def scrape_detail_url(self, url: str) -> Optional[PropertyListing]:
        """Scrape a single Zillow property detail page by URL."""
        cache_params = {"type": "detail", "url": url}
        cached = await self._cache.get("zillow_detail", cache_params)
        if cached:
            return PropertyListing(**cached)

        context, page = await self._browser.new_stealth_page()
        try:
            success = await self._browser.safe_goto(page, url, ZILLOW_DOMAIN)
            if not success:
                logger.warning("Failed to load Zillow detail page: %s", url)
                return None

            await page.wait_for_timeout(3000)

            # Primary: extract from __NEXT_DATA__.props.pageProps.gdpClientCache
            listing = await self._extract_detail_from_gdp(page)

            # Fallback: recursive zpid search in __NEXT_DATA__
            if not listing:
                permissive = RegionConfig(
                    name="detail", center_lat=0, center_lng=0,
                    min_price=0, max_price=999_999_999, min_beds=0, max_beds=100,
                )
                results = await self._extract_from_next_data(page, permissive)
                if results:
                    listing = results[0]

            # Final fallback: DOM scraping
            if not listing:
                permissive = RegionConfig(
                    name="detail", center_lat=0, center_lng=0,
                    min_price=0, max_price=999_999_999, min_beds=0, max_beds=100,
                )
                dom_results = await self._scrape_from_dom(page, permissive)
                if dom_results:
                    listing = dom_results[0]

            if listing:
                await self._cache.set(
                    "zillow_detail", cache_params, listing.model_dump(mode="json")
                )

            return listing

        except Exception as e:
            logger.error("Error scraping Zillow detail %s: %s", url, e)
            return None
        finally:
            await context.close()

    async def _extract_detail_from_gdp(self, page: Any) -> Optional[PropertyListing]:
        """Extract from __NEXT_DATA__.props.pageProps.gdpClientCache on detail page."""
        json_data = await self._browser.extract_json_from_script(page, "__NEXT_DATA__")
        if not json_data:
            return None

        try:
            cache = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("gdpClientCache", {})
            )
            for _key, val in cache.items():
                if isinstance(val, str):
                    try:
                        data = json.loads(val)
                        if isinstance(data, dict) and "property" in data:
                            return self._property_data_to_listing(data["property"])
                    except json.JSONDecodeError:
                        pass
                elif isinstance(val, dict) and "property" in val:
                    return self._property_data_to_listing(val["property"])
        except Exception as e:
            logger.debug("gdpClientCache detail extraction failed: %s", e)

        return None
