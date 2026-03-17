"""Report and analysis result data models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from str_researcher.models.comp import AmenityMatrix, PurchaseComp, STRComp
from str_researcher.models.financials import InvestmentMetrics
from str_researcher.models.marketing import MarketingPlan
from str_researcher.models.property import PropertyListing
from str_researcher.models.str_performance import (
    DualRevenueEstimate,
    MarketMetrics,
)


class PurchaseItem(BaseModel):
    """A specific item to purchase with a product link."""

    item_name: str
    quantity: int = 1
    estimated_cost: float
    product_url: str = ""  # Link to Amazon, Wayfair, etc.
    store: str = ""  # "Amazon", "Wayfair", "Home Depot", etc.
    notes: str = ""


class DesignRecommendation(BaseModel):
    """A single design or renovation recommendation."""

    category: str  # "Interior", "Amenity", "Outdoor", "Theme"
    recommendation: str
    estimated_cost_low: float
    estimated_cost_high: float
    priority: Literal["must_have", "high_impact", "nice_to_have"]
    reasoning: str
    purchase_items: list[PurchaseItem] = Field(default_factory=list)


class ScopeOfWork(BaseModel):
    """Complete renovation and design scope of work."""

    design_direction: str  # AI-generated narrative
    theme_concept: str
    target_guest_profile: str
    recommendations: list[DesignRecommendation] = Field(default_factory=list)
    total_budget_low: float = 0.0
    total_budget_high: float = 0.0
    amenity_gap_analysis: list[AmenityMatrix] = Field(default_factory=list)

    def calculate_totals(self) -> None:
        """Recalculate total budget from individual recommendations."""
        self.total_budget_low = sum(r.estimated_cost_low for r in self.recommendations)
        self.total_budget_high = sum(
            r.estimated_cost_high for r in self.recommendations
        )


class AnalysisResult(BaseModel):
    """Complete analysis result for a single property."""

    property: PropertyListing
    revenue_estimate: DualRevenueEstimate
    market_metrics: MarketMetrics
    investment_metrics: dict[str, InvestmentMetrics] = Field(
        default_factory=dict
    )  # keyed by scenario name
    purchase_comps: list[PurchaseComp] = Field(default_factory=list)
    str_comps: list[STRComp] = Field(default_factory=list)
    scope_of_work: Optional[ScopeOfWork] = None
    marketing_plan: Optional[MarketingPlan] = None
    investment_score: float = 0.0
    investment_rank: int = 0
    investment_narrative: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.now)

    # Report URLs (populated after report generation)
    sheet_url: Optional[str] = None
    scope_doc_url: Optional[str] = None
    marketing_doc_url: Optional[str] = None
