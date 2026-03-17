"""SQLite-based caching layer for scraped and API data."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from str_researcher.utils.logging import get_logger

logger = get_logger("cache")

CACHE_DIR = Path(__file__).parent.parent.parent.parent / ".cache"
DEFAULT_DB_PATH = CACHE_DIR / "str_cache.db"


class ScraperCache:
    """Disk-based cache using SQLite for scraped data."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, ttl_hours: int = 24):
        self._db_path = db_path
        self._ttl_seconds = ttl_hours * 3600
        self._db: Optional[aiosqlite.Connection] = None

    async def __aenter__(self) -> "ScraperCache":
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        await self._db.commit()
        logger.info("Cache initialized at %s", self._db_path)
        return self

    async def __aexit__(self, *args) -> None:
        if self._db:
            await self._db.close()

    @staticmethod
    def _make_key(source: str, params: dict) -> str:
        """Generate a cache key from source name and query parameters."""
        param_str = json.dumps(params, sort_keys=True)
        raw = f"{source}:{param_str}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, source: str, params: dict) -> Optional[dict | list]:
        """Retrieve cached data if it exists and hasn't expired."""
        if not self._db:
            return None

        key = self._make_key(source, params)
        cursor = await self._db.execute(
            "SELECT data, created_at FROM cache WHERE cache_key = ?",
            (key,),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        data_str, created_at = row
        age = time.time() - created_at

        if age > self._ttl_seconds:
            # Expired
            await self._db.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
            await self._db.commit()
            logger.debug("Cache expired for %s (age=%.0fs)", source, age)
            return None

        logger.debug("Cache hit for %s (age=%.0fs)", source, age)
        return json.loads(data_str)

    async def set(self, source: str, params: dict, data: dict | list) -> None:
        """Store data in the cache."""
        if not self._db:
            return

        key = self._make_key(source, params)
        data_str = json.dumps(data, default=str)

        await self._db.execute(
            """
            INSERT OR REPLACE INTO cache (cache_key, source, data, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (key, source, data_str, time.time()),
        )
        await self._db.commit()
        logger.debug("Cached data for %s", source)

    async def invalidate(self, source: Optional[str] = None) -> int:
        """Invalidate cache entries. If source is None, clear all."""
        if not self._db:
            return 0

        if source:
            cursor = await self._db.execute(
                "DELETE FROM cache WHERE source = ?", (source,)
            )
        else:
            cursor = await self._db.execute("DELETE FROM cache")

        await self._db.commit()
        count = cursor.rowcount
        logger.info("Invalidated %d cache entries (source=%s)", count, source or "all")
        return count

    async def stats(self) -> dict:
        """Get cache statistics."""
        if not self._db:
            return {"entries": 0, "sources": []}

        cursor = await self._db.execute("SELECT COUNT(*) FROM cache")
        row = await cursor.fetchone()
        total = row[0] if row else 0

        cursor = await self._db.execute(
            "SELECT source, COUNT(*) FROM cache GROUP BY source"
        )
        sources = {row[0]: row[1] for row in await cursor.fetchall()}

        return {"entries": total, "sources": sources}
