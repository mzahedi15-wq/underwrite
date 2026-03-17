"""Abstract base class for scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from str_researcher.config import RegionConfig


class BaseScraper(ABC):
    """Base class for all data scrapers."""

    @abstractmethod
    async def scrape(self, config: RegionConfig, **kwargs: Any) -> list[BaseModel]:
        """Scrape data for the given region configuration."""
        ...

    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source."""
        ...
