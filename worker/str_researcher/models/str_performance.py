"""STR performance and market data models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MonthlyProjection(BaseModel):
    """Monthly revenue projection."""

    month: int  # 1-12
    revenue: float
    adr: float
    occupancy_rate: float
    available_nights: int = 30


class STREstimate(BaseModel):
    """Revenue estimate for a property as a short-term rental."""

    address: str
    annual_revenue: float
    adr: float
    occupancy_rate: float
    monthly_projections: list[MonthlyProjection] = Field(default_factory=list)
    comparable_listing_ids: list[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    source: Literal["airdna_rentalizer", "comp_derived"]


class DualRevenueEstimate(BaseModel):
    """Combined revenue estimate from both AirDNA and Airbnb comp analysis."""

    airdna_estimate: Optional[STREstimate] = None
    comp_estimate: Optional[STREstimate] = None

    # Reconciled values
    conservative_revenue: float = 0.0  # Lower of the two
    moderate_revenue: float = 0.0  # Blended average
    aggressive_revenue: float = 0.0  # Higher / top 10% comp performance

    divergence_pct: float = 0.0  # % difference between the two estimates
    needs_manual_review: bool = False  # True if divergence > 20%

    @property
    def primary_adr(self) -> float:
        """Use AirDNA ADR if available, else comp-derived."""
        if self.airdna_estimate:
            return self.airdna_estimate.adr
        if self.comp_estimate:
            return self.comp_estimate.adr
        return 0.0

    @property
    def primary_occupancy(self) -> float:
        """Use AirDNA occupancy if available, else comp-derived."""
        if self.airdna_estimate:
            return self.airdna_estimate.occupancy_rate
        if self.comp_estimate:
            return self.comp_estimate.occupancy_rate
        return 0.0

    @property
    def moderate_adr(self) -> float:
        """Blended ADR for the moderate scenario."""
        adrs = []
        if self.airdna_estimate:
            adrs.append(self.airdna_estimate.adr)
        if self.comp_estimate:
            adrs.append(self.comp_estimate.adr)
        return sum(adrs) / len(adrs) if adrs else 0.0

    @property
    def moderate_occupancy(self) -> float:
        """Blended occupancy for the moderate scenario."""
        occs = []
        if self.airdna_estimate:
            occs.append(self.airdna_estimate.occupancy_rate)
        if self.comp_estimate:
            occs.append(self.comp_estimate.occupancy_rate)
        return sum(occs) / len(occs) if occs else 0.0

    @property
    def conservative_adr(self) -> float:
        """ADR for the conservative scenario.

        When two sources exist, returns the lower; when only one source,
        applies a 15% haircut to reflect conservative underwriting.
        """
        adrs = []
        if self.airdna_estimate:
            adrs.append(self.airdna_estimate.adr)
        if self.comp_estimate:
            adrs.append(self.comp_estimate.adr)
        if len(adrs) >= 2:
            return min(adrs)
        elif adrs:
            return adrs[0] * 0.85
        return 0.0

    @property
    def conservative_occupancy(self) -> float:
        """Occupancy for the conservative scenario."""
        occs = []
        if self.airdna_estimate:
            occs.append(self.airdna_estimate.occupancy_rate)
        if self.comp_estimate:
            occs.append(self.comp_estimate.occupancy_rate)
        if len(occs) >= 2:
            return min(occs)
        elif occs:
            return max(occs[0] * 0.90, 0.35)
        return 0.0

    @property
    def aggressive_adr(self) -> float:
        """ADR for the aggressive scenario.

        When two sources exist, returns the higher; when only one source,
        derives from aggressive_revenue / (365 * aggressive_occupancy).
        """
        adrs = []
        if self.airdna_estimate:
            adrs.append(self.airdna_estimate.adr)
        if self.comp_estimate:
            adrs.append(self.comp_estimate.adr)
        if len(adrs) >= 2:
            return max(adrs)
        elif adrs:
            agg_occ = self.aggressive_occupancy
            if agg_occ > 0 and self.aggressive_revenue > 0:
                return self.aggressive_revenue / (365 * agg_occ)
            return adrs[0] * 1.15
        return 0.0

    @property
    def aggressive_occupancy(self) -> float:
        """Occupancy for the aggressive scenario."""
        occs = []
        if self.airdna_estimate:
            occs.append(self.airdna_estimate.occupancy_rate)
        if self.comp_estimate:
            occs.append(self.comp_estimate.occupancy_rate)
        if len(occs) >= 2:
            return max(occs)
        elif occs:
            return min(occs[0] * 1.10, 0.90)
        return 0.0


class MarketMetrics(BaseModel):
    """Market-level STR performance data."""

    market_id: str
    market_name: str
    adr: float
    occupancy_rate: float
    revpar: float
    active_listing_count: int = 0
    revenue_growth_yoy: Optional[float] = None
    seasonality_index: dict[int, float] = Field(
        default_factory=dict
    )  # month -> relative demand (1.0 = avg)
