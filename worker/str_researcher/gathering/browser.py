"""Shared Playwright browser manager with stealth configuration."""

from __future__ import annotations

import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
try:
    from playwright_stealth import Stealth
except (ImportError, ModuleNotFoundError):
    # playwright-stealth requires pkg_resources (setuptools) which may be absent
    # in slim Python images. Fall back to a no-op so the worker still starts.
    class Stealth:  # type: ignore[no-redef]
        async def apply_stealth_async(self, page) -> None:
            pass

from str_researcher.utils.logging import get_logger
from str_researcher.utils.rate_limiter import RateLimiter

logger = get_logger("browser")

# Realistic viewport sizes
VIEWPORT_SIZES = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]

# Realistic user agents
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class BrowserManager:
    """Manages a Playwright browser instance with stealth and rate limiting."""

    def __init__(self, proxy_url: Optional[str] = None, headless: bool = True):
        self._proxy_url = proxy_url
        self._headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._rate_limiter = RateLimiter()

    async def __aenter__(self) -> "BrowserManager":
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {
            "headless": self._headless,
        }
        if self._proxy_url:
            launch_kwargs["proxy"] = {"server": self._proxy_url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        logger.info("Browser launched (headless=%s)", self._headless)
        return self

    async def __aexit__(self, *args) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def new_context(self) -> BrowserContext:
        """Create a new browser context with stealth configuration."""
        if not self._browser:
            raise RuntimeError("Browser not initialized. Use async with.")

        viewport = random.choice(VIEWPORT_SIZES)
        user_agent = random.choice(USER_AGENTS)

        context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="light",
            java_script_enabled=True,
        )

        return context

    async def new_stealth_page(self) -> tuple[BrowserContext, Page]:
        """Create a new context and page with stealth applied."""
        stealth = Stealth()
        context = await self.new_context()
        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        return context, page

    async def safe_goto(
        self,
        page: Page,
        url: str,
        domain: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> bool:
        """Navigate to URL with rate limiting and error handling.

        Returns True if navigation succeeded, False if blocked/failed.
        """
        await self._rate_limiter.acquire(domain)

        try:
            response = await page.goto(url, wait_until=wait_until, timeout=timeout)

            if response is None:
                logger.warning("No response for %s", url)
                return False

            status = response.status

            if status == 403 or status == 429:
                logger.warning("Blocked (HTTP %d) at %s", status, url)
                return False

            if status >= 400:
                logger.warning("HTTP %d for %s", status, url)
                return False

            # Check for common anti-bot indicators
            content = await page.content()
            block_indicators = [
                "captcha",
                "blocked",
                "access denied",
                "rate limit",
                "please verify",
                "cf-browser-verification",
            ]
            content_lower = content.lower()
            for indicator in block_indicators:
                if indicator in content_lower and len(content) < 5000:
                    logger.warning("Possible block detected (%s) at %s", indicator, url)
                    return False

            return True

        except Exception as e:
            logger.error("Navigation error for %s: %s", url, e)
            return False

    async def extract_json_from_script(
        self, page: Page, script_id: str
    ) -> Optional[dict]:
        """Extract JSON data from a <script> tag by ID."""
        try:
            import json

            script_content = await page.evaluate(
                f"""
                (() => {{
                    const el = document.getElementById('{script_id}');
                    return el ? el.textContent : null;
                }})()
                """
            )
            if script_content:
                return json.loads(script_content)
        except Exception as e:
            logger.debug("Failed to extract JSON from script#%s: %s", script_id, e)
        return None

    async def intercept_xhr_responses(
        self, page: Page, url_pattern: str, timeout: int = 15000
    ) -> list[dict]:
        """Capture XHR/fetch responses matching a URL pattern.

        Returns list of parsed JSON response bodies.
        """
        import asyncio
        import json

        captured: list[dict] = []

        async def on_response(response):
            if url_pattern in response.url:
                try:
                    body = await response.json()
                    captured.append(body)
                except Exception:
                    pass

        page.on("response", on_response)

        # Wait for responses to come in
        try:
            await asyncio.sleep(timeout / 1000)
        except asyncio.CancelledError:
            pass

        page.remove_listener("response", on_response)
        return captured
