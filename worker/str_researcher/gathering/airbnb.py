"""Airbnb scraper for STR competitive analysis."""

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

logger = get_logger("airbnb")

AIRBNB_DOMAIN = "airbnb.com"


class AirbnbScraper(BaseScraper):
    """Scrapes Airbnb listings for competitive analysis."""

    def __init__(self, browser: BrowserManager, cache: ScraperCache):
        self._browser = browser
        self._cache = cache

    def source_name(self) -> str:
        return "airbnb"

    async def scrape(self, config: RegionConfig, **kwargs: Any) -> list[STRComp]:
        """Scrape Airbnb listings near the target region."""
        cache_params = {
            "type": "str_comps",
            "region": config.name,
            "lat": config.center_lat,
            "lng": config.center_lng,
            "radius": config.radius_miles,
        }

        cached = await self._cache.get("airbnb_comps", cache_params)
        if cached:
            logger.info("Using cached Airbnb comps (%d)", len(cached))
            return [STRComp(**item) for item in cached]

        comps = await self._scrape_search(config)

        if comps:
            await self._cache.set(
                "airbnb_comps",
                cache_params,
                [c.model_dump(mode="json") for c in comps],
            )

        logger.info("Scraped %d Airbnb comps for %s", len(comps), config.name)
        return comps

    async def _scrape_search(self, config: RegionConfig) -> list[STRComp]:
        """Scrape Airbnb search results by intercepting API responses."""
        context, page = await self._browser.new_stealth_page()
        comps: list[STRComp] = []
        captured_data: list[dict] = []

        async def _on_response(response):
            """Intercept Airbnb API responses containing search results."""
            try:
                url = response.url
                # Airbnb's search API endpoints
                if any(kw in url for kw in (
                    "StaysSearch", "ExploreSearch", "SearchResults",
                    "/api/v3/", "staysSearch",
                )):
                    ct = response.headers.get("content-type", "")
                    if "json" in ct and response.status == 200:
                        try:
                            body = await response.json()
                            captured_data.append(body)
                            logger.debug(
                                "Captured Airbnb API response (%d bytes) from %s",
                                len(str(body)), url[:80],
                            )
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", _on_response)

        try:
            url = self._build_search_url(config)
            logger.info("Loading Airbnb search: %s", url[:120])
            success = await self._browser.safe_goto(page, url, AIRBNB_DOMAIN)

            if not success:
                logger.warning("Failed to load Airbnb search page")
            else:
                # Wait for API responses to arrive
                await page.wait_for_timeout(8000)

                # Scroll to trigger lazy-loaded results
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(1500)

            # --- Strategy 1: Process intercepted API data ---
            for data in captured_data:
                listings = self._extract_listings_from_api(data)
                for listing_data in listings:
                    comp = self._data_to_comp(listing_data, config)
                    if comp:
                        comps.append(comp)

            if comps:
                logger.info("Strategy 1 (API interception): %d comps", len(comps))

            # --- Strategy 2: Extract from embedded page state ---
            if not comps:
                logger.info("API interception got 0 comps, trying page state...")
                comps = await self._extract_from_page_state(page, config)
                if comps:
                    logger.info("Strategy 2 (page state): %d comps", len(comps))

            # --- Strategy 3: DOM scraping ---
            if not comps:
                logger.info("Page state got 0 comps, trying DOM scrape...")
                comps = await self._scrape_from_dom(page, config)
                if comps:
                    logger.info("Strategy 3 (DOM): %d comps", len(comps))

            # Paginate if we got results (up to 3 pages)
            if comps:
                for page_num in range(2, 4):
                    if len(comps) >= 60:
                        break
                    captured_data.clear()
                    next_url = self._build_search_url(config, page=page_num)
                    success = await self._browser.safe_goto(
                        page, next_url, AIRBNB_DOMAIN
                    )
                    if not success:
                        break
                    await page.wait_for_timeout(5000)

                    for data in captured_data:
                        listings = self._extract_listings_from_api(data)
                        for listing_data in listings:
                            comp = self._data_to_comp(listing_data, config)
                            if comp:
                                comps.append(comp)

        except Exception as e:
            logger.error("Error scraping Airbnb: %s", e)
        finally:
            await context.close()

        if not comps:
            logger.warning(
                "Airbnb scraper returned 0 comps for %s — "
                "site may have blocked the request or changed structure",
                config.name,
            )

        return comps

    def _build_search_url(self, config: RegionConfig, page: int = 1) -> str:
        """Build an Airbnb search URL with map bounds."""
        lat_offset = config.radius_miles / 69.0
        lng_offset = config.radius_miles / 54.6

        ne_lat = config.center_lat + lat_offset
        ne_lng = config.center_lng + lng_offset
        sw_lat = config.center_lat - lat_offset
        sw_lng = config.center_lng - lng_offset

        params = {
            "ne_lat": f"{ne_lat:.6f}",
            "ne_lng": f"{ne_lng:.6f}",
            "sw_lat": f"{sw_lat:.6f}",
            "sw_lng": f"{sw_lng:.6f}",
            "zoom": 12,
            "zoom_level": 12,
            "search_by_map": "true",
            "tab_id": "home_tab",
            "refinement_paths[]": "/homes",
            "search_type": "filter",
        }

        if config.min_beds > 1:
            params["min_bedrooms"] = config.min_beds

        if page > 1:
            params["items_offset"] = (page - 1) * 20

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://www.airbnb.com/s/homes?{query}"

    @staticmethod
    def _extract_listings_from_api(data: dict) -> list[dict]:
        """Extract listing objects from Airbnb's API response."""
        listings = []

        def _search(obj, depth=0):
            if depth > 25:
                return
            if isinstance(obj, dict):
                # Airbnb API: result objects contain a "listing" key
                if "listing" in obj and isinstance(obj["listing"], dict):
                    listing = obj["listing"]
                    # Merge pricing/rating from parent into listing
                    for key in ("pricingQuote", "avgRatingLocalized",
                                "avgRating", "reviewsCount"):
                        if key in obj:
                            listing[key] = obj[key]
                    listings.append(listing)
                elif "id" in obj and "name" in obj and (
                    "avgRating" in obj or "roomType" in obj or "lat" in obj
                ):
                    listings.append(obj)
                elif "searchResults" in obj:
                    for r in obj["searchResults"]:
                        _search(r, depth + 1)
                elif "results" in obj and isinstance(obj["results"], list):
                    for r in obj["results"]:
                        _search(r, depth + 1)
                elif "sections" in obj and isinstance(obj["sections"], list):
                    for s in obj["sections"]:
                        _search(s, depth + 1)
                elif "items" in obj and isinstance(obj["items"], list):
                    for item in obj["items"]:
                        _search(item, depth + 1)
                else:
                    for v in obj.values():
                        _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(data)
        return listings

    async def _extract_from_page_state(
        self, page: Any, config: RegionConfig
    ) -> list[STRComp]:
        """Extract listing data from Airbnb's embedded page state."""
        comps = []

        try:
            script_content = await page.evaluate(
                """
                (() => {
                    // Method 1: data-deferred-state (current Airbnb)
                    const ds = document.querySelectorAll('script[data-deferred-state]');
                    for (const s of ds) {
                        if (s.textContent && s.textContent.length > 100)
                            return s.textContent;
                    }
                    // Method 2: __NEXT_DATA__
                    const nd = document.getElementById('__NEXT_DATA__');
                    if (nd && nd.textContent.length > 500) return nd.textContent;
                    // Method 3: large JSON scripts
                    const scripts = document.querySelectorAll(
                        'script[type="application/json"]'
                    );
                    for (const s of scripts) {
                        if (s.textContent && s.textContent.length > 2000 &&
                            (s.textContent.includes('listing') ||
                             s.textContent.includes('avgRating')))
                            return s.textContent;
                    }
                    return null;
                })()
                """
            )

            if script_content:
                data = json.loads(script_content)
                listings = self._extract_listings_from_api(data)
                logger.info("Page state: found %d listing objects", len(listings))
                for listing_data in listings:
                    comp = self._data_to_comp(listing_data, config)
                    if comp:
                        comps.append(comp)
            else:
                logger.warning("No embedded state data found on Airbnb page")

        except Exception as e:
            logger.warning("Failed to extract Airbnb page state: %s", e)

        return comps

    async def _scrape_from_dom(
        self, page: Any, config: RegionConfig
    ) -> list[STRComp]:
        """Fallback: scrape listing data from Airbnb DOM."""
        comps = []

        try:
            # Find all links to /rooms/ — most reliable selector
            room_links = await page.query_selector_all("a[href*='/rooms/']")
            logger.info("DOM scrape: found %d room links", len(room_links))

            seen_urls: set[str] = set()
            for link in room_links:
                try:
                    href = await link.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Get the parent card container
                    parent = await link.evaluate_handle(
                        """el => el.closest('[role="group"]')
                            || el.closest('[data-testid]')
                            || el.parentElement?.parentElement?.parentElement"""
                    )
                    if not parent:
                        continue

                    text = await parent.evaluate("el => el.textContent") or ""

                    # Extract price — detect total vs per-night
                    price_match = re.search(r"\$(\d[\d,]*)", text)
                    if not price_match:
                        continue
                    raw_price = float(price_match.group(1).replace(",", ""))
                    if raw_price <= 0:
                        continue

                    # Check if this is a total price ("for X nights")
                    nights_match = re.search(
                        r"\$[\d,]+\s+(?:for\s+)?(\d+)\s+night", text, re.I
                    )
                    if nights_match:
                        num_nights = int(nights_match.group(1))
                        nightly_rate = raw_price / num_nights
                    elif re.search(r"per\s*night|/\s*night", text, re.I):
                        nightly_rate = raw_price
                    else:
                        # Airbnb defaults to 2-night total display
                        nightly_rate = raw_price / 2

                    # Extract beds
                    beds = 0
                    bed_match = re.search(r"(\d+)\s*bed", text, re.I)
                    if bed_match:
                        beds = int(bed_match.group(1))

                    # Title — first non-empty line
                    title = text.strip().split("\n")[0].strip()[:100]

                    listing_url = (
                        f"https://www.airbnb.com{href}"
                        if href.startswith("/")
                        else href
                    )

                    # Rating
                    review_score = None
                    review_count = 0
                    rating_match = re.search(r"([\d.]+)\s*\((\d+)\)", text)
                    if rating_match:
                        review_score = float(rating_match.group(1))
                        review_count = int(rating_match.group(2))

                    comp = STRComp(
                        platform="airbnb",
                        listing_url=listing_url,
                        title=title,
                        beds=beds,
                        baths=1.0,
                        accommodates=beds * 2 + 2 if beds else 4,
                        nightly_rate_avg=nightly_rate,
                        annual_revenue_est=nightly_rate * 365 * 0.65,
                        review_count=review_count,
                        review_score=review_score,
                    )
                    comps.append(comp)

                except Exception:
                    continue

        except Exception as e:
            logger.warning("Airbnb DOM scraping failed: %s", e)

        return comps

    @staticmethod
    def _extract_nightly_rate(data: dict, name: str) -> float:
        """Extract per-night rate from Airbnb listing data.

        Airbnb search results show "total before taxes" for the searched
        dates (typically 2-3 nights).  We need to detect this and convert
        to a true per-night rate.

        Priority order:
        1. Explicit ``pricePerNight`` or ``rate.amount`` from pricing API
        2. Divide total display price by detected number of nights
        3. Parse "$X / night" or "$X per night" from name/qualifier text
        4. Fall back to raw price / 2 (Airbnb defaults to 2-night search)
        """
        nightly_rate = 0.0
        total_price = 0.0
        num_nights = 0  # 0 = unknown

        pricing = data.get("pricingQuote", {}) or data.get("pricing", {})
        if isinstance(pricing, dict):
            # Best case: explicit per-night rate
            per_night = pricing.get("pricePerNight", 0)
            if isinstance(per_night, (int, float)) and per_night > 0:
                nightly_rate = float(per_night)
            elif isinstance(per_night, str):
                m = re.search(r"[\d,]+", per_night)
                if m:
                    nightly_rate = float(m.group().replace(",", ""))

            # rate.amount — usually per-night from API
            if not nightly_rate:
                rate_obj = pricing.get("rate", {})
                if isinstance(rate_obj, dict):
                    amt = rate_obj.get("amount", 0)
                    if isinstance(amt, (int, float)) and amt > 0:
                        nightly_rate = float(amt)
                    elif isinstance(amt, str):
                        m = re.search(r"[\d,]+", amt)
                        if m:
                            nightly_rate = float(m.group().replace(",", ""))

            # structuredStayDisplayPrice — total price display
            display = pricing.get("structuredStayDisplayPrice", {})
            if isinstance(display, dict):
                primary = display.get("primaryLine", {})
                if isinstance(primary, dict):
                    price_str = (
                        primary.get("price", "")
                        or primary.get("discountedPrice", "")
                        or ""
                    )
                    qualifier = primary.get("qualifier", "") or ""
                    # Detect "for X nights" → total price
                    nights_m = re.search(r"for\s+(\d+)\s+night", qualifier, re.I)
                    if nights_m:
                        num_nights = int(nights_m.group(1))
                    # Detect "per night" → already nightly
                    if re.search(r"per\s*night|/\s*night", qualifier, re.I):
                        num_nights = 1

                    if isinstance(price_str, str) and not nightly_rate:
                        m = re.search(r"\$?([\d,]+)", price_str)
                        if m:
                            total_price = float(m.group(1).replace(",", ""))

                # Secondary line may contain the per-night breakdown
                secondary = display.get("secondaryLine", {})
                if isinstance(secondary, dict) and not nightly_rate:
                    sec_text = secondary.get("price", "") or ""
                    if isinstance(sec_text, str) and re.search(
                        r"per\s*night|/\s*night", sec_text, re.I
                    ):
                        m = re.search(r"\$?([\d,]+)", sec_text)
                        if m:
                            nightly_rate = float(m.group(1).replace(",", ""))

        # Fallback: raw price field
        if not nightly_rate and not total_price:
            raw_price = data.get("price", 0)
            if isinstance(raw_price, str):
                m = re.search(r"\$?([\d,]+)", raw_price)
                total_price = float(m.group(1).replace(",", "")) if m else 0.0
            elif isinstance(raw_price, (int, float)):
                total_price = float(raw_price)

        # Parse "for X nights" from the listing title / name
        if not num_nights and name:
            m = re.search(r"\$[\d,]+\s+(?:for\s+)?(\d+)\s+night", name, re.I)
            if m:
                num_nights = int(m.group(1))

        # Convert total → nightly if we have a total but no per-night
        if not nightly_rate and total_price > 0:
            if num_nights > 0:
                nightly_rate = total_price / num_nights
            else:
                # Airbnb defaults to 2-night search when no dates specified
                nightly_rate = total_price / 2
                logger.debug(
                    "Assuming 2-night total for %s: $%.0f → $%.0f/night",
                    name[:40], total_price, nightly_rate,
                )

        return nightly_rate

    @staticmethod
    def _extract_beds(data: dict, name: str) -> int:
        """Extract bedroom count from API data with text fallback.

        Uses increasingly aggressive strategies:
        1. Explicit API keys (bedrooms, beds, etc.)
        2. Room type heuristics (private room = 1)
        3. Listing title regex
        4. Structured room configuration
        5. Deep search through ALL string values in the data dict
        6. Guest capacity heuristic (capacity ÷ 2)
        """
        bed_pattern = re.compile(
            r"(\d+)\s*[-–]?\s*(?:bed(?:room)?s?|br)\b", re.I,
        )

        # ── Strategy 1: Explicit API keys ──
        for key in ("bedrooms", "beds", "bedroom_count", "bedroomCount",
                     "numberOfBedrooms", "num_bedrooms"):
            val = data.get(key)
            if val and int(val) > 0:
                return int(val)

        # ── Strategy 2: Room type heuristic ──
        room_type = data.get("roomType", "") or data.get("room_type", "")
        if "private room" in str(room_type).lower():
            return 1

        # ── Strategy 3: Parse from listing name/title ──
        if name:
            m = bed_pattern.search(name)
            if m:
                return int(m.group(1))

        # ── Strategy 4: Structured room labels ──
        for key in ("rooms", "roomConfiguration", "listingRooms"):
            rooms = data.get(key, [])
            if isinstance(rooms, list):
                bed_rooms = [
                    r for r in rooms
                    if isinstance(r, dict)
                    and "bed" in str(r.get("label", "")).lower()
                ]
                if bed_rooms:
                    return len(bed_rooms)

        # ── Strategy 5: Deep search — scan ALL string values for bed count ──
        # Airbnb embeds bed/bath info in subtitle, badge, or display fields
        # that may not use predictable key names.
        def _scan_strings(obj, depth=0):
            """Walk the data dict and search every string for bed counts."""
            if depth > 10:
                return 0
            if isinstance(obj, str) and len(obj) > 3:
                m = bed_pattern.search(obj)
                if m:
                    return int(m.group(1))
            elif isinstance(obj, dict):
                # Prioritise subtitle / badge / display keys
                priority_keys = [
                    k for k in obj
                    if any(s in k.lower() for s in
                           ("subtitle", "badge", "display", "detail",
                            "label", "description", "summary", "amenity"))
                ]
                other_keys = [k for k in obj if k not in priority_keys]
                for k in priority_keys + other_keys:
                    result = _scan_strings(obj[k], depth + 1)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = _scan_strings(item, depth + 1)
                    if result:
                        return result
            return 0

        deep_beds = _scan_strings(data)
        if deep_beds > 0:
            return deep_beds

        # ── Strategy 6: Guest capacity heuristic ──
        capacity = data.get("personCapacity") or data.get("guestCapacity") or 0
        if capacity and int(capacity) > 0:
            return max(1, int(capacity) // 2)

        return 0

    @staticmethod
    def _deep_find(data: dict, keys: list[str], max_depth: int = 8) -> Any:
        """Recursively search nested dicts for a key, returning first truthy match."""
        def _search(obj, depth=0):
            if depth > max_depth:
                return None
            if isinstance(obj, dict):
                for k in keys:
                    val = obj.get(k)
                    if val is not None and val != "" and val != 0 and val != []:
                        return val
                for v in obj.values():
                    result = _search(v, depth + 1)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = _search(item, depth + 1)
                    if result is not None:
                        return result
            return None
        return _search(data)

    @staticmethod
    def _extract_review_data(data: dict) -> tuple[Optional[float], int]:
        """Extract review score and count using deep search."""
        review_score = None
        review_count = 0

        # --- Direct keys ---
        for key in ("avgRating", "guestSatisfactionOverall",
                    "overallRating", "rating", "starRating"):
            val = data.get(key)
            if val is not None:
                try:
                    score = float(val) if not isinstance(val, str) else None
                    if score and score > 0:
                        review_score = score
                        break
                except (ValueError, TypeError):
                    pass

        for key in ("reviewsCount", "visibleReviewCount", "numberOfReviews",
                    "reviewCount", "totalReviews", "reviews_count"):
            val = data.get(key)
            if val and int(val) > 0:
                review_count = int(val)
                break

        # avgRatingLocalized (e.g., "4.92 (125)")
        avg_loc = data.get("avgRatingLocalized", "")
        if isinstance(avg_loc, str) and avg_loc:
            if not review_score:
                m = re.search(r"([\d.]+)", avg_loc)
                if m:
                    review_score = float(m.group(1))
            if not review_count:
                m = re.search(r"\((\d+)\)", avg_loc)
                if m:
                    review_count = int(m.group(1))

        # --- Deep search through nested data ---
        if not review_score:
            deep_score = AirbnbScraper._deep_find(
                data,
                ["avgRating", "overallRating", "guestSatisfactionOverall",
                 "starRating", "rating"],
            )
            if deep_score is not None:
                try:
                    review_score = float(deep_score)
                except (ValueError, TypeError):
                    if isinstance(deep_score, str):
                        m = re.search(r"([\d.]+)", deep_score)
                        if m:
                            review_score = float(m.group(1))

        if not review_count:
            deep_count = AirbnbScraper._deep_find(
                data,
                ["reviewsCount", "visibleReviewCount", "numberOfReviews",
                 "reviewCount", "totalReviews"],
            )
            if deep_count is not None:
                try:
                    review_count = int(deep_count)
                except (ValueError, TypeError):
                    pass

        # --- Parse from all strings (e.g., "4.92 · 125 reviews") ---
        if not review_score or not review_count:
            review_pattern = re.compile(
                r"([\d.]+)\s*[·•★]\s*(\d+)\s*reviews?", re.I
            )
            def _scan_for_review(obj, depth=0):
                nonlocal review_score, review_count
                if depth > 6:
                    return
                if isinstance(obj, str) and len(obj) > 3:
                    m = review_pattern.search(obj)
                    if m:
                        if not review_score:
                            review_score = float(m.group(1))
                        if not review_count:
                            review_count = int(m.group(2))
                        return
                elif isinstance(obj, dict):
                    for k in obj:
                        if any(s in k.lower() for s in
                               ("rating", "review", "badge", "subtitle",
                                "accessibility", "label")):
                            _scan_for_review(obj[k], depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        _scan_for_review(item, depth + 1)
            _scan_for_review(data)

        # Normalize score (Airbnb uses both 0-5 and 0-100 scales)
        if review_score and review_score > 5:
            review_score = review_score / 20  # Convert 0-100 → 0-5

        return review_score, review_count

    @staticmethod
    def _extract_superhost(data: dict) -> bool:
        """Extract superhost status using deep search."""
        # Direct keys
        for key in ("isSuperhost", "isSuperHost", "is_superhost", "superhost"):
            val = data.get(key)
            if val is True:
                return True

        # Deep search
        deep_val = AirbnbScraper._deep_find(
            data, ["isSuperhost", "isSuperHost", "is_superhost"]
        )
        if deep_val is True:
            return True

        # Check in badge/label text
        def _scan_superhost(obj, depth=0):
            if depth > 6:
                return False
            if isinstance(obj, str) and "superhost" in obj.lower():
                return True
            elif isinstance(obj, dict):
                for k in ("badge", "badgeText", "superhost", "hostBadge",
                           "hostProfileBadge", "badgeType"):
                    if k in obj:
                        if _scan_superhost(obj[k], depth + 1):
                            return True
                for v in obj.values():
                    if _scan_superhost(v, depth + 1):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if _scan_superhost(item, depth + 1):
                        return True
            return False

        return _scan_superhost(data)

    @staticmethod
    def _extract_amenities(data: dict) -> list[str]:
        """Extract amenities list using deep search."""
        amenities = []

        # Direct keys
        for key in ("amenities", "listingAmenities", "previewAmenities",
                     "previewAmenityNames", "amenityIds"):
            raw = data.get(key, [])
            if isinstance(raw, list) and raw:
                for a in raw:
                    if isinstance(a, str) and a:
                        amenities.append(a)
                    elif isinstance(a, dict):
                        name = (a.get("name", "") or a.get("tag", "")
                                or a.get("title", "") or a.get("text", ""))
                        if name:
                            amenities.append(name)
                if amenities:
                    return amenities

        # Deep search for amenity arrays
        deep_amenities = AirbnbScraper._deep_find(
            data,
            ["previewAmenities", "amenities", "listingAmenities",
             "previewAmenityNames"],
        )
        if isinstance(deep_amenities, list):
            for a in deep_amenities:
                if isinstance(a, str) and a:
                    amenities.append(a)
                elif isinstance(a, dict):
                    name = (a.get("name", "") or a.get("tag", "")
                            or a.get("title", "") or a.get("text", ""))
                    if name:
                        amenities.append(name)

        # Parse from structured display text (e.g., "Pool · Hot tub · Wifi")
        if not amenities:
            common_amenities = {
                "pool", "hot tub", "wifi", "kitchen", "parking",
                "air conditioning", "washer", "dryer", "fireplace",
                "gym", "ev charger", "bbq", "fire pit", "game room",
                "lake view", "mountain view", "ocean view", "sauna",
                "jacuzzi", "pets allowed", "self check-in",
            }
            def _scan_amenity_text(obj, depth=0):
                if depth > 6:
                    return
                if isinstance(obj, str) and len(obj) > 3:
                    text_lower = obj.lower()
                    for am in common_amenities:
                        if am in text_lower and am not in [a.lower() for a in amenities]:
                            amenities.append(am.title())
                elif isinstance(obj, dict):
                    for k in obj:
                        if any(s in k.lower() for s in
                               ("amenity", "highlight", "preview", "feature")):
                            _scan_amenity_text(obj[k], depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        _scan_amenity_text(item, depth + 1)
            _scan_amenity_text(data)

        return amenities

    @staticmethod
    def _data_to_comp(data: dict, config: RegionConfig) -> Optional[STRComp]:
        """Convert Airbnb listing data dict to an STRComp."""
        try:
            listing_id = data.get("id", "")
            name = data.get("name", "") or data.get("title", "")
            if not name:
                return None

            # --- Bedrooms ---
            beds = AirbnbScraper._extract_beds(data, name)
            baths = data.get("bathrooms", 1.0) or 1.0
            accommodates = (
                data.get("personCapacity", 0)
                or data.get("guestCapacity", 0)
                or (beds * 2 + 2 if beds else 4)
            )

            # --- Nightly rate (handles total-price display) ---
            nightly_rate = AirbnbScraper._extract_nightly_rate(data, name)
            if nightly_rate <= 0:
                return None

            # --- Reviews (deep search) ---
            review_score, review_count = AirbnbScraper._extract_review_data(data)

            # --- Superhost (deep search) ---
            superhost = AirbnbScraper._extract_superhost(data)

            # --- Amenities (deep search) ---
            amenities = AirbnbScraper._extract_amenities(data)

            # Location
            lat = data.get("lat") or data.get("latitude")
            lng = data.get("lng") or data.get("longitude")
            if not lat:
                coord = data.get("coordinate", {}) or data.get("location", {})
                if isinstance(coord, dict):
                    lat = coord.get("latitude") or coord.get("lat")
                    lng = coord.get("longitude") or coord.get("lng")

            distance = 0.0
            if lat and lng:
                distance = haversine_distance(
                    config.center_lat, config.center_lng,
                    float(lat), float(lng),
                )

            # Photos
            photos = []
            for p in (data.get("photos", []) or data.get("contextualPictures", []))[:5]:
                if isinstance(p, str):
                    photos.append(p)
                elif isinstance(p, dict):
                    photos.append(p.get("picture", "") or p.get("url", ""))

            url = f"https://www.airbnb.com/rooms/{listing_id}" if listing_id else ""

            # Occupancy estimate from calendar
            occupancy_est = None
            calendar = data.get("calendarAvailability", {})
            if calendar:
                available = calendar.get("availableDays", 0)
                total = calendar.get("totalDays", 60)
                if total > 0:
                    occupancy_est = 1.0 - (available / total)

            # Revenue estimate
            if occupancy_est:
                annual_revenue = nightly_rate * 365 * occupancy_est
            else:
                annual_revenue = nightly_rate * 365 * 0.65

            return STRComp(
                platform="airbnb",
                listing_url=url,
                title=name,
                beds=int(beds),
                baths=float(baths),
                accommodates=int(accommodates),
                nightly_rate_avg=float(nightly_rate),
                annual_revenue_est=annual_revenue,
                occupancy_est=occupancy_est,
                review_count=int(review_count),
                review_score=float(review_score) if review_score else None,
                superhost=superhost,
                amenities=[a for a in amenities if a],
                photo_urls=[p for p in photos if p],
                distance_miles=distance,
                lat=float(lat) if lat else None,
                lng=float(lng) if lng else None,
            )

        except Exception as e:
            logger.debug("Failed to convert Airbnb data to comp: %s", e)
            return None
