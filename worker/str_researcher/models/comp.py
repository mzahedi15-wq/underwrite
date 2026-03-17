"""Comparable property data models."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PurchaseComp(BaseModel):
    """A comparable recently-sold property for purchase price analysis."""

    address: str
    sale_price: int
    sale_date: date
    beds: int
    baths: float
    sqft: Optional[int] = None
    price_per_sqft: Optional[float] = None
    distance_miles: float = 0.0
    source: str = "redfin"
    adjustments: dict[str, float] = Field(default_factory=dict)
    adjusted_price: Optional[int] = None

    def apply_adjustments(self) -> int:
        """Calculate adjusted price from base sale price + adjustments."""
        total_adjustment = sum(self.adjustments.values())
        self.adjusted_price = int(self.sale_price + total_adjustment)
        return self.adjusted_price


class STRComp(BaseModel):
    """A comparable short-term rental listing from Airbnb or VRBO."""

    platform: Literal["airbnb", "vrbo"]
    listing_url: str
    title: str
    beds: int
    baths: float
    accommodates: int
    nightly_rate_avg: float
    monthly_revenue_est: Optional[float] = None
    annual_revenue_est: Optional[float] = None
    occupancy_est: Optional[float] = None
    review_count: int = 0
    review_score: Optional[float] = None
    superhost: bool = False
    amenities: list[str] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)
    distance_miles: float = 0.0
    is_top_performer: bool = False
    lat: Optional[float] = None
    lng: Optional[float] = None

    @property
    def performance_score(self) -> float:
        """Score combining revenue and quality for ranking."""
        revenue = self.annual_revenue_est or (self.nightly_rate_avg * 365 * 0.65)
        quality = min(self.review_score or 4.0, 5.0) / 5.0
        return revenue * quality


class AmenityMatrix(BaseModel):
    """Tracks amenity prevalence in top performers vs all comps."""

    amenity_name: str
    count_in_top_10_pct: int = 0
    count_in_all_comps: int = 0
    prevalence_top_pct: float = 0.0  # % of top 10% that have it
    prevalence_all_pct: float = 0.0  # % of all comps that have it

    @property
    def is_differentiator(self) -> bool:
        """True if the amenity is much more common in top performers."""
        return self.prevalence_top_pct > self.prevalence_all_pct + 0.20
