"""Financial analysis data models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FinancingScenario(BaseModel):
    """A financing scenario (conventional, DSCR, or cash)."""

    name: str  # "Conventional", "DSCR", "Cash"
    purchase_price: int
    down_payment: float
    loan_amount: float
    interest_rate: float
    monthly_payment: float  # P&I only (0 for cash)
    closing_costs: float
    renovation_furnishing: float = 0.0  # Renovation + furnishing budget
    total_cash_needed: float  # Down + closing + furnishing


class MonthlyCashflow(BaseModel):
    """Monthly cashflow projection for one month."""

    month: int  # 1-12
    gross_revenue: float
    management_fee: float
    cleaning_costs: float
    platform_fees: float
    mortgage: float
    taxes: float
    insurance: float
    hoa: float
    utilities: float
    maintenance: float
    net_cashflow: float

    @property
    def total_expenses(self) -> float:
        return (
            self.management_fee
            + self.cleaning_costs
            + self.platform_fees
            + self.mortgage
            + self.taxes
            + self.insurance
            + self.hoa
            + self.utilities
            + self.maintenance
        )


class SensitivityCase(BaseModel):
    """One cell in the sensitivity matrix."""

    label: str  # e.g., "Revenue -20% / Expenses +10%"
    revenue_factor: float  # 0.80, 1.00, 1.20, etc.
    expense_factor: float  # 0.90, 1.00, 1.10, etc.
    annual_revenue: float
    annual_expenses: float
    noi: float
    annual_net_cashflow: float
    cash_on_cash_return: float
    cap_rate: float
    dscr: Optional[float] = None  # None for Cash scenario (no debt)


class SensitivityAnalysis(BaseModel):
    """Revenue × expense sensitivity matrix for a financing scenario."""

    scenario_name: str  # "Conventional", "DSCR", "Cash"
    cases: list[SensitivityCase] = Field(default_factory=list)

    # Convenience lookups
    revenue_levels: list[str] = Field(default_factory=list)  # ["-20%", "-10%", "Base", "+10%", "+20%"]
    expense_levels: list[str] = Field(default_factory=list)  # ["Base", "+10%", "+20%"]

    # Seasonal risk metrics
    peak_months_revenue_pct: float = 0.0  # % of annual revenue from top 3 months
    off_peak_normalized_annual: float = 0.0  # Revenue if peak premiums stripped
    seasonal_risk_note: str = ""  # Human-readable seasonal concentration note


class SuggestedOffer(BaseModel):
    """AI/algorithm-generated offer recommendation."""

    offer_price: int
    rationale: str  # Human-readable explanation
    discount_pct: float  # % below list price (e.g., 0.07 = 7% below)
    factors: dict[str, str] = Field(default_factory=dict)  # Factor → weight


class InvestmentMetrics(BaseModel):
    """Complete investment analysis for one property + one financing scenario."""

    annual_gross_revenue: float
    annual_expenses: float
    noi: float  # Net Operating Income (before debt service)
    cap_rate: float
    cash_on_cash_return: float
    dscr: Optional[float] = None  # Debt Service Coverage Ratio (None for Cash)
    break_even_occupancy: float
    monthly_cashflows: list[MonthlyCashflow] = Field(default_factory=list)
    financing: FinancingScenario
    annual_net_cashflow: float = 0.0
    sensitivity: Optional[SensitivityAnalysis] = None
    suggested_offer: Optional[SuggestedOffer] = None

    @property
    def monthly_avg_cashflow(self) -> float:
        if not self.monthly_cashflows:
            return 0.0
        return sum(m.net_cashflow for m in self.monthly_cashflows) / len(
            self.monthly_cashflows
        )
