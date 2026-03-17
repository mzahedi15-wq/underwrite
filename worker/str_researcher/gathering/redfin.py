"""Redfin scraper for property listings and purchase comps."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import quote, urlencode

from str_researcher.config import RegionConfig
from str_researcher.gathering.base import BaseScraper
from str_researcher.gathering.browser import BrowserManager
from str_researcher.gathering.cache import ScraperCache
from str_researcher.models.comp import PurchaseComp
from str_researcher.models.property import PropertyListing
from str_researcher.utils.logging import get_logger

logger = get_logger("redfin")

REDFIN_DOMAIN = "redfin.com"


class RedfinScraper(BaseScraper):
    """Scrapes property listings and purchase comps from Redfin."""

    def __init__(self, browser: BrowserManager, cache: ScraperCache):
        self._browser = browser
        self._cache = cache

    def source_name(self) -> str:
        return "redfin"

    async def scrape(self, config: RegionConfig, **kwargs: Any) -> list[PropertyListing]:
        """Scrape active listings from Redfin for the given region."""
        cache_params = {
            "type": "listings",
            "region": config.name,
            "min_price": config.min_price,
            "max_price": config.max_price,
            "min_beds": config.min_beds,
            "max_beds": config.max_beds,
        }

        # Check cache
        cached = await self._cache.get("redfin_listings", cache_params)
        if cached:
            logger.info("Using cached Redfin listings (%d)", len(cached))
            return [PropertyListing(**item) for item in cached]

        listings = []

        if config.redfin_search_url:
            listings = await self._scrape_from_url(config.redfin_search_url, config)
        else:
            listings = await self._scrape_from_api(config)

        # Cache results
        if listings:
            await self._cache.set(
                "redfin_listings",
                cache_params,
                [listing.model_dump(mode="json") for listing in listings],
            )

        logger.info("Scraped %d listings from Redfin", len(listings))
        return listings

    async def scrape_purchase_comps(
        self,
        config: RegionConfig,
        months_back: int = 6,
    ) -> list[PurchaseComp]:
        """Scrape recently sold properties for purchase comp analysis."""
        cache_params = {
            "type": "sold",
            "region": config.name,
            "months_back": months_back,
            "lat": config.center_lat,
            "lng": config.center_lng,
        }

        cached = await self._cache.get("redfin_sold", cache_params)
        if cached:
            logger.info("Using cached Redfin sold comps (%d)", len(cached))
            return [PurchaseComp(**item) for item in cached]

        comps = await self._scrape_sold_from_api(config, months_back)

        if comps:
            await self._cache.set(
                "redfin_sold",
                cache_params,
                [comp.model_dump(mode="json") for comp in comps],
            )

        logger.info("Scraped %d purchase comps from Redfin", len(comps))
        return comps

    async def _scrape_from_url(
        self, url: str, config: RegionConfig
    ) -> list[PropertyListing]:
        """Scrape listings from a user-provided Redfin search URL."""
        context, page = await self._browser.new_stealth_page()
        listings = []

        try:
            success = await self._browser.safe_goto(page, url, REDFIN_DOMAIN)
            if not success:
                logger.warning("Failed to load Redfin search URL")
                return []

            # Wait for listing cards to load
            await page.wait_for_selector(
                '[data-rf-test-id="photo-card"],.HomeCard',
                timeout=10000,
            )

            # Try to extract data from Redfin's inline JSON
            listings = await self._extract_listings_from_page(page, config)

            # Handle pagination
            page_num = 1
            while len(listings) < config.max_price:  # Rough limit
                page_num += 1
                next_btn = await page.query_selector('button[data-rf-test-id="react-data-paginate-next"]')
                if not next_btn:
                    break

                await next_btn.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                new_listings = await self._extract_listings_from_page(page, config)
                if not new_listings:
                    break
                listings.extend(new_listings)
                logger.debug("Redfin page %d: +%d listings", page_num, len(new_listings))

        except Exception as e:
            logger.error("Error scraping Redfin: %s", e)
        finally:
            await context.close()

        return listings

    async def _scrape_from_api(self, config: RegionConfig) -> list[PropertyListing]:
        """Scrape listings using Redfin's hidden API endpoints.

        Strategy: navigate to redfin.com first to establish cookies/context,
        then fetch the GIS API as an XHR from within the page (same-origin).
        """
        context, page = await self._browser.new_stealth_page()
        listings = []

        try:
            # Navigate to Redfin first to establish session
            success = await self._browser.safe_goto(
                page, "https://www.redfin.com", REDFIN_DOMAIN
            )
            if not success:
                logger.warning("Could not reach redfin.com")
                return []

            await page.wait_for_timeout(2000)

            # Fetch GIS API as XHR from within the Redfin page context
            api_url = self._build_gis_api_url(config)
            raw = await page.evaluate(
                """async (url) => {
                    try {
                        const resp = await fetch(url);
                        return await resp.text();
                    } catch (e) {
                        return "FETCH_ERROR: " + e.message;
                    }
                }""",
                api_url,
            )

            if raw and not raw.startswith("FETCH_ERROR"):
                listings = self._parse_gis_response_raw(raw, config)
                logger.info("Redfin GIS API returned %d listings", len(listings))
            else:
                logger.warning("Redfin GIS fetch failed: %s", raw[:200] if raw else "empty")
                # Fallback: try search page scraping
                search_url = f"https://www.redfin.com/city/{quote(config.name)}"
                success = await self._browser.safe_goto(page, search_url, REDFIN_DOMAIN)
                if success:
                    listings = await self._extract_listings_from_page(page, config)

        except Exception as e:
            logger.error("Error with Redfin API: %s", e)
        finally:
            await context.close()

        return listings

    async def _scrape_sold_from_api(
        self, config: RegionConfig, months_back: int
    ) -> list[PurchaseComp]:
        """Scrape recently sold properties using Redfin's API."""
        context, page = await self._browser.new_stealth_page()
        comps = []

        try:
            success = await self._browser.safe_goto(
                page, "https://www.redfin.com", REDFIN_DOMAIN
            )
            if not success:
                return []

            await page.wait_for_timeout(2000)

            api_url = self._build_gis_api_url(config, sold=True, months_back=months_back)
            raw = await page.evaluate(
                """async (url) => {
                    try {
                        const resp = await fetch(url);
                        return await resp.text();
                    } catch (e) {
                        return "FETCH_ERROR: " + e.message;
                    }
                }""",
                api_url,
            )

            if raw and not raw.startswith("FETCH_ERROR"):
                comps = self._parse_sold_response_raw(raw, config)
            else:
                logger.warning("Redfin sold GIS fetch failed")

        except Exception as e:
            logger.error("Error scraping Redfin sold: %s", e)
        finally:
            await context.close()

        return comps

    def _build_gis_api_url(
        self,
        config: RegionConfig,
        sold: bool = False,
        months_back: int = 6,
    ) -> str:
        """Build a Redfin GIS API URL for the given region."""
        # Calculate bounding box from center + radius
        # Rough conversion: 1 degree lat ≈ 69 miles, 1 degree lng varies
        lat_offset = config.radius_miles / 69.0
        lng_offset = config.radius_miles / 54.6  # Approximate for US latitudes

        params = {
            "al": 1,
            "market": "false",
            "min_stories": 1,
            "num_homes": 350,
            "ord": "redfin-recommended-asc",
            "page_number": 1,
            "poly": self._make_polygon(
                config.center_lat,
                config.center_lng,
                lat_offset,
                lng_offset,
            ),
            "sf": "1,2,3,5,6,7",
            "status": 9 if sold else 1,  # 9 = sold, 1 = active
            "uipt": "1,2,3,4,5,6",  # Property types
            "v": 8,
        }

        if config.min_price > 0:
            params["min_price"] = config.min_price
        if config.max_price < 5_000_000:
            params["max_price"] = config.max_price
        if config.min_beds > 1:
            params["min_num_beds"] = config.min_beds

        if sold and months_back:
            params["sold_within_days"] = months_back * 30

        base = "https://www.redfin.com/stingray/api/gis"
        return f"{base}?{urlencode(params)}"

    @staticmethod
    def _make_polygon(
        center_lat: float, center_lng: float, lat_off: float, lng_off: float
    ) -> str:
        """Create a polygon string for Redfin's GIS API."""
        points = [
            f"{center_lng - lng_off} {center_lat - lat_off}",
            f"{center_lng + lng_off} {center_lat - lat_off}",
            f"{center_lng + lng_off} {center_lat + lat_off}",
            f"{center_lng - lng_off} {center_lat + lat_off}",
            f"{center_lng - lng_off} {center_lat - lat_off}",
        ]
        return ",".join(points)

    def _parse_gis_response_raw(
        self, raw: str, config: RegionConfig
    ) -> list[PropertyListing]:
        """Parse raw GIS API response text (from XHR fetch) into PropertyListing objects."""
        listings = []
        try:
            json_str = raw
            if json_str.startswith("{}&&"):
                json_str = json_str[4:]

            data = json.loads(json_str)
            homes = data.get("payload", {}).get("homes", [])

            for home in homes:
                try:
                    listing = self._home_to_listing(home)
                    if listing and self._matches_filters(listing, config):
                        listings.append(listing)
                except Exception as e:
                    logger.debug("Failed to parse home: %s", e)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Redfin GIS response: %s", e)

        return listings

    def _parse_gis_response(
        self, content: str, config: RegionConfig
    ) -> list[PropertyListing]:
        """Parse GIS response from an HTML page context (legacy fallback)."""
        # Strip HTML wrapper if present
        json_str = content
        body_match = re.search(r"<body[^>]*>(.*?)</body>", json_str, re.DOTALL)
        if body_match:
            json_str = body_match.group(1).strip()
        return self._parse_gis_response_raw(json_str, config)

    def _parse_sold_response_raw(
        self, raw: str, config: RegionConfig
    ) -> list[PurchaseComp]:
        """Parse raw sold GIS API response text into PurchaseComp objects."""
        comps = []
        try:
            json_str = raw
            if json_str.startswith("{}&&"):
                json_str = json_str[4:]

            data = json.loads(json_str)
            homes = data.get("payload", {}).get("homes", [])

            for home in homes:
                try:
                    comp = self._home_to_comp(home, config)
                    if comp:
                        comps.append(comp)
                except Exception as e:
                    logger.debug("Failed to parse sold home: %s", e)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Redfin sold response: %s", e)

        return comps

    def _parse_sold_response(
        self, content: str, config: RegionConfig
    ) -> list[PurchaseComp]:
        """Parse sold response from an HTML page context (legacy fallback)."""
        json_str = content
        body_match = re.search(r"<body[^>]*>(.*?)</body>", json_str, re.DOTALL)
        if body_match:
            json_str = body_match.group(1).strip()
        return self._parse_sold_response_raw(json_str, config)

    @staticmethod
    def _home_to_listing(home: dict) -> Optional[PropertyListing]:
        """Convert a Redfin home object to a PropertyListing."""
        price = home.get("price", {}).get("value") or home.get("listingPrice")
        if not price:
            return None

        address_data = home.get("address", {}) or {}
        street = home.get("streetLine", {}).get("value", "") or address_data.get(
            "streetAddress", ""
        )
        city = home.get("city", "") or address_data.get("city", "")
        state = home.get("state", "") or address_data.get("stateOrProvinceCode", "")
        zip_code = home.get("zip", "") or address_data.get("postalCode", "")

        if not street:
            return None

        beds = home.get("beds", 0)
        baths = home.get("baths", 0.0)
        sqft = home.get("sqFt", {}).get("value") or home.get("sqFt")
        if isinstance(sqft, dict):
            sqft = sqft.get("value")

        lat = home.get("latLong", {}).get("value", {}).get("latitude") or home.get("latitude")
        lng = home.get("latLong", {}).get("value", {}).get("longitude") or home.get("longitude")

        url = home.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://www.redfin.com{url}"

        return PropertyListing(
            source="redfin",
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
            lot_sqft=home.get("lotSize", {}).get("value") if isinstance(home.get("lotSize"), dict) else None,
            year_built=home.get("yearBuilt", {}).get("value") if isinstance(home.get("yearBuilt"), dict) else None,
            property_type=str(home.get("propertyType", "single_family")),
            hoa_monthly=home.get("hoa", {}).get("value") if isinstance(home.get("hoa"), dict) else None,
            days_on_market=home.get("dom", {}).get("value") if isinstance(home.get("dom"), dict) else None,
        )

    @staticmethod
    def _home_to_comp(home: dict, config: RegionConfig) -> Optional[PurchaseComp]:
        """Convert a Redfin sold home to a PurchaseComp."""
        price = home.get("price", {}).get("value") or home.get("soldPrice")
        if not price:
            return None

        street = home.get("streetLine", {}).get("value", "")
        if not street:
            return None

        beds = home.get("beds", 0)
        baths = home.get("baths", 0.0)
        sqft = home.get("sqFt", {}).get("value") if isinstance(home.get("sqFt"), dict) else home.get("sqFt")

        sold_date_val = home.get("soldDate")
        if sold_date_val:
            try:
                sold_date = datetime.fromtimestamp(sold_date_val / 1000).date()
            except (ValueError, TypeError, OSError):
                sold_date = date.today()
        else:
            sold_date = date.today()

        lat = home.get("latLong", {}).get("value", {}).get("latitude")
        lng = home.get("latLong", {}).get("value", {}).get("longitude")

        from str_researcher.utils.geocoding import haversine_distance

        distance = 0.0
        if lat and lng:
            distance = haversine_distance(
                config.center_lat, config.center_lng, lat, lng
            )

        price_per_sqft = None
        if sqft and sqft > 0:
            price_per_sqft = int(price) / int(sqft)

        return PurchaseComp(
            address=street,
            sale_price=int(price),
            sale_date=sold_date,
            beds=int(beds) if beds else 0,
            baths=float(baths) if baths else 0.0,
            sqft=int(sqft) if sqft else None,
            price_per_sqft=price_per_sqft,
            distance_miles=distance,
            source="redfin",
        )

    async def _extract_listings_from_page(
        self, page: Any, config: RegionConfig
    ) -> list[PropertyListing]:
        """Extract listing data from a Redfin search results page."""
        listings = []

        # Try to extract from page's React state
        try:
            data = await page.evaluate(
                """
                (() => {
                    const state = window.__reactServerState || window.__NEXT_DATA__;
                    if (state) return JSON.stringify(state);
                    return null;
                })()
                """
            )
            if data:
                parsed = json.loads(data)
                # Navigate through Redfin's React state to find homes
                homes = self._find_homes_in_state(parsed)
                for home in homes:
                    listing = self._home_to_listing(home)
                    if listing and self._matches_filters(listing, config):
                        listings.append(listing)
        except Exception as e:
            logger.debug("Failed to extract React state: %s", e)

        # Fallback: scrape from DOM
        if not listings:
            listings = await self._scrape_listings_from_dom(page, config)

        return listings

    async def _scrape_listings_from_dom(
        self, page: Any, config: RegionConfig
    ) -> list[PropertyListing]:
        """Fallback: scrape listing data from DOM elements."""
        listings = []

        cards = await page.query_selector_all(".HomeCard, .MapHomeCard")
        for card in cards:
            try:
                price_el = await card.query_selector(".homecardV2Price, .bp-Homecard__Price--value")
                addr_el = await card.query_selector(".homeAddressV2, .bp-Homecard__Address")
                stats_el = await card.query_selector(".HomeStatsV2, .bp-Homecard__Stats")
                link_el = await card.query_selector("a[href]")

                if not (price_el and addr_el):
                    continue

                price_text = (await price_el.inner_text()).strip()
                price = int(re.sub(r"[^\d]", "", price_text))

                addr_text = (await addr_el.inner_text()).strip()
                parts = addr_text.split(",")
                street = parts[0].strip() if parts else addr_text
                city = parts[1].strip() if len(parts) > 1 else ""
                state_zip = parts[2].strip() if len(parts) > 2 else ""
                state = state_zip.split()[0] if state_zip else ""
                zip_code = state_zip.split()[1] if len(state_zip.split()) > 1 else ""

                beds, baths, sqft = 0, 0.0, None
                if stats_el:
                    stats_text = await stats_el.inner_text()
                    bed_match = re.search(r"(\d+)\s*[Bb]ed", stats_text)
                    bath_match = re.search(r"([\d.]+)\s*[Bb]ath", stats_text)
                    sqft_match = re.search(r"([\d,]+)\s*[Ss]q\s*[Ff]t", stats_text)
                    if bed_match:
                        beds = int(bed_match.group(1))
                    if bath_match:
                        baths = float(bath_match.group(1))
                    if sqft_match:
                        sqft = int(sqft_match.group(1).replace(",", ""))

                url = ""
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        url = f"https://www.redfin.com{href}" if href.startswith("/") else href

                listing = PropertyListing(
                    source="redfin",
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
                logger.debug("Failed to parse DOM card: %s", e)

        return listings

    @staticmethod
    def _find_homes_in_state(state: dict) -> list[dict]:
        """Recursively search for home data in Redfin's React state."""
        homes = []

        def _search(obj, depth=0):
            if depth > 10:
                return
            if isinstance(obj, dict):
                if "homes" in obj and isinstance(obj["homes"], list):
                    homes.extend(obj["homes"])
                elif "listPrice" in obj or "price" in obj:
                    homes.append(obj)
                else:
                    for v in obj.values():
                        _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(state)
        return homes

    @staticmethod
    def _matches_filters(listing: PropertyListing, config: RegionConfig) -> bool:
        """Check if a listing matches the region's filter criteria."""
        if listing.list_price < config.min_price or listing.list_price > config.max_price:
            return False
        if listing.beds < config.min_beds or listing.beds > config.max_beds:
            return False
        return True

    async def scrape_detail_url(self, url: str) -> Optional[PropertyListing]:
        """Scrape a single Redfin property detail page by URL."""
        cache_params = {"type": "detail", "url": url}
        cached = await self._cache.get("redfin_detail", cache_params)
        if cached:
            return PropertyListing(**cached)

        context, page = await self._browser.new_stealth_page()
        try:
            success = await self._browser.safe_goto(page, url, REDFIN_DOMAIN)
            if not success:
                logger.warning("Failed to load Redfin detail page: %s", url)
                return None

            await page.wait_for_timeout(3000)

            listing = await self._extract_detail_from_page(page, url)

            if listing:
                await self._cache.set(
                    "redfin_detail", cache_params, listing.model_dump(mode="json")
                )

            return listing

        except Exception as e:
            logger.error("Error scraping Redfin detail %s: %s", url, e)
            return None
        finally:
            await context.close()

    async def _extract_detail_from_page(
        self, page: Any, url: str
    ) -> Optional[PropertyListing]:
        """Extract property data from a Redfin detail page."""
        # Strategy 1: LD+JSON structured data
        scripts = await page.query_selector_all("script[type='application/ld+json']")
        for script in scripts:
            try:
                content = await script.inner_text()
                ld = json.loads(content)
                home_type = ld.get("@type", "")
                if home_type in (
                    "SingleFamilyResidence",
                    "Residence",
                    "ApartmentComplex",
                    "House",
                ):
                    addr = ld.get("address", {})
                    offers = ld.get("offers", {})
                    price = offers.get("price") if offers else None
                    if isinstance(price, str):
                        price = int(re.sub(r"[^\d]", "", price)) if price else 0

                    street = addr.get("streetAddress", "")
                    city = addr.get("addressLocality", "")
                    state = addr.get("addressRegion", "")
                    zip_code = addr.get("postalCode", "")

                    if street and price:
                        return PropertyListing(
                            source="redfin",
                            source_url=url,
                            address=street,
                            city=city,
                            state=state,
                            zip_code=str(zip_code),
                            list_price=int(price),
                        )
            except Exception:
                continue

        # Strategy 2: Redfin's embedded JS data blob
        try:
            page_data = await page.evaluate(
                """() => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const t = s.textContent || '';
                        if (t.includes('"beds"') && t.includes('"price"') && t.length > 500) {
                            return t;
                        }
                    }
                    return null;
                }"""
            )
            if page_data:
                price_match = re.search(r'"price"\s*:\s*\{"value"\s*:\s*(\d+)', page_data)
                beds_match = re.search(r'"beds"\s*:\s*(\d+)', page_data)
                baths_match = re.search(r'"baths"\s*:\s*([\d.]+)', page_data)
                sqft_match = re.search(r'"sqFt"\s*:\s*\{"value"\s*:\s*(\d+)', page_data)
                lat_match = re.search(r'"latitude"\s*:\s*([\d.-]+)', page_data)
                lng_match = re.search(r'"longitude"\s*:\s*([\d.-]+)', page_data)
                addr_match = re.search(r'"streetLine"\s*:\s*\{"value"\s*:\s*"([^"]+)"', page_data)
                city_match = re.search(r'"city"\s*:\s*"([^"]+)"', page_data)
                state_match = re.search(r'"state"\s*:\s*"([^"]+)"', page_data)
                zip_match = re.search(r'"zip"\s*:\s*"([^"]+)"', page_data)

                if price_match:
                    return PropertyListing(
                        source="redfin",
                        source_url=url,
                        address=addr_match.group(1) if addr_match else "",
                        city=city_match.group(1) if city_match else "",
                        state=state_match.group(1) if state_match else "",
                        zip_code=zip_match.group(1) if zip_match else "",
                        list_price=int(price_match.group(1)),
                        beds=int(beds_match.group(1)) if beds_match else 0,
                        baths=float(baths_match.group(1)) if baths_match else 0.0,
                        sqft=int(sqft_match.group(1)) if sqft_match else None,
                        lat=float(lat_match.group(1)) if lat_match else None,
                        lng=float(lng_match.group(1)) if lng_match else None,
                    )
        except Exception as e:
            logger.debug("Redfin JS data extraction failed: %s", e)

        return None
