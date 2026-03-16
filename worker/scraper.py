"""
Property + STR comp scraping utilities.
Uses Playwright for JS-rendered pages (Zillow, Redfin).
"""

import re
import json
import asyncio
from typing import Optional
from playwright.async_api import async_playwright


async def scrape_property(url: str) -> dict:
    """Scrape listing data from a Zillow or Redfin URL."""
    if "zillow.com" in url:
        return await _scrape_zillow(url)
    elif "redfin.com" in url:
        return await _scrape_redfin(url)
    else:
        raise ValueError(f"Unsupported listing URL: {url}")


async def _scrape_zillow(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector("[data-test-id='home-details-chip']", timeout=10000)

            # Extract __NEXT_DATA__ JSON which Zillow embeds in the page
            next_data = await page.evaluate("""
                () => {
                    const el = document.getElementById('__NEXT_DATA__');
                    return el ? JSON.parse(el.textContent) : null;
                }
            """)

            if next_data:
                return _parse_zillow_next_data(next_data)

            # Fallback: scrape visible DOM elements
            return await _scrape_zillow_dom(page)

        finally:
            await browser.close()


def _parse_zillow_next_data(data: dict) -> dict:
    """Parse Zillow's embedded JSON blob."""
    try:
        props = (
            data.get("props", {})
            .get("pageProps", {})
            .get("gdpClientCache", {})
        )
        # Find the property key
        for key, val in props.items():
            if "property" in val:
                prop = val["property"]
                return {
                    "address": prop.get("streetAddress", ""),
                    "city": prop.get("city", ""),
                    "state": prop.get("state", ""),
                    "zip": prop.get("zipcode", ""),
                    "list_price": prop.get("price"),
                    "beds": prop.get("bedrooms"),
                    "baths": prop.get("bathrooms"),
                    "sqft": prop.get("livingArea"),
                    "lot_sqft": prop.get("lotAreaValue"),
                    "year_built": prop.get("yearBuilt"),
                    "lat": prop.get("latitude"),
                    "lon": prop.get("longitude"),
                    "description": prop.get("description", ""),
                    "home_type": prop.get("homeType", ""),
                }
    except Exception:
        pass
    return {}


async def _scrape_zillow_dom(page) -> dict:
    """DOM-based fallback scraper for Zillow."""
    data = {}
    try:
        price_el = await page.query_selector("[data-test-id='price']")
        if price_el:
            price_text = await price_el.inner_text()
            data["list_price"] = int(re.sub(r"[^\d]", "", price_text))

        address_el = await page.query_selector("h1[class*='Address']")
        if address_el:
            data["address"] = await address_el.inner_text()

    except Exception:
        pass
    return data


async def _scrape_redfin(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Redfin embeds property data in a script tag
            scripts = await page.query_selector_all("script[type='application/ld+json']")
            for script in scripts:
                content = await script.inner_text()
                try:
                    ld = json.loads(content)
                    if ld.get("@type") == "SingleFamilyResidence":
                        addr = ld.get("address", {})
                        return {
                            "address": addr.get("streetAddress", ""),
                            "city": addr.get("addressLocality", ""),
                            "state": addr.get("addressRegion", ""),
                            "zip": addr.get("postalCode", ""),
                            "list_price": ld.get("offers", {}).get("price"),
                            "beds": ld.get("numberOfRooms"),
                            "description": ld.get("description", ""),
                        }
                except Exception:
                    continue
        finally:
            await browser.close()
    return {}


async def scrape_str_comps(lat: Optional[float], lon: Optional[float], beds: int) -> dict:
    """
    Pull STR comparable data.
    In production: integrate AirDNA API or scrape AirDNA/Rabbu.
    This stub returns realistic placeholder data for development.
    """
    if not lat or not lon:
        return _mock_comps(beds)

    # TODO: Replace with real AirDNA API call
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(
    #         "https://api.airdna.co/v1/market/search",
    #         params={"lat": lat, "lon": lon, "radius": 1, "beds": beds},
    #         headers={"X-AUTH-TOKEN": os.environ["AIRDNA_API_KEY"]},
    #     )
    #     return resp.json()

    return _mock_comps(beds)


def _mock_comps(beds: int) -> dict:
    """Realistic placeholder STR comp data for development."""
    base_adr = 180 + (beds * 45)
    base_occupancy = 0.68 + (beds * 0.02)
    return {
        "radius_miles": 1.0,
        "comp_count": 12,
        "median_adr": base_adr,
        "median_occupancy": round(base_occupancy, 3),
        "median_annual_revenue": int(base_adr * base_occupancy * 365),
        "percentile_25_revenue": int(base_adr * 0.55 * 365),
        "percentile_75_revenue": int(base_adr * 1.15 * 365),
        "top_amenities": ["pool", "hot_tub", "mountain_view", "fast_wifi"],
        "source": "mock_development",
    }
