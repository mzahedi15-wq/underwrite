"""Property listing data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PropertyListing(BaseModel):
    """A property listing from Zillow, Redfin, or Realtor.com."""

    source: Literal["zillow", "redfin", "realtor"]
    source_url: str
    address: str
    city: str
    state: str
    zip_code: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    list_price: int
    beds: int
    baths: float
    sqft: Optional[int] = None
    lot_sqft: Optional[int] = None
    year_built: Optional[int] = None
    property_type: str = "single_family"
    hoa_monthly: Optional[float] = None
    days_on_market: Optional[int] = None
    description: Optional[str] = None
    photo_urls: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)

    @property
    def price_per_sqft(self) -> Optional[float]:
        if self.sqft and self.sqft > 0:
            return self.list_price / self.sqft
        return None

    @property
    def full_address(self) -> str:
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"

    @property
    def accommodates(self) -> int:
        """Estimate max guests: 2 per bedroom + 2 for common area."""
        return self.beds * 2 + 2
