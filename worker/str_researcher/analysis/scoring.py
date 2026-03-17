"""Investment scoring and property ranking."""

from __future__ import annotations

from str_researcher.config import ScoringWeights
from str_researcher.models.report import AnalysisResult
from str_researcher.utils.logging import get_logger

logger = get_logger("scoring")


class InvestmentScorer:
    """Scores and ranks properties by investment potential."""

    def __init__(self, weights: ScoringWeights):
        self.weights = weights

    def score_property(self, result: AnalysisResult) -> float:
        """Calculate a 0-100 investment score for a property."""
        scores: dict[str, float] = {}

        # 1. Cash-on-Cash Return (best scenario)
        best_coc = max(
            (m.cash_on_cash_return for m in result.investment_metrics.values()),
            default=0,
        )
        scores["cash_on_cash"] = self._normalize_coc(best_coc)

        # 2. Cap Rate
        best_cap = max(
            (m.cap_rate for m in result.investment_metrics.values()),
            default=0,
        )
        scores["cap_rate"] = self._normalize_cap_rate(best_cap)

        # 3. Revenue Upside (gap between moderate and aggressive/top 10%)
        rev = result.revenue_estimate
        if rev.moderate_revenue > 0:
            upside_ratio = rev.aggressive_revenue / rev.moderate_revenue
            scores["revenue_upside"] = min((upside_ratio - 1.0) * 200, 100)
        else:
            scores["revenue_upside"] = 0

        # 4. Renovation Efficiency
        # Higher score if estimated renovation cost is low relative to revenue gain
        if result.scope_of_work and rev.moderate_revenue > 0:
            avg_reno_cost = (
                result.scope_of_work.total_budget_low
                + result.scope_of_work.total_budget_high
            ) / 2
            if avg_reno_cost > 0:
                rev_lift = rev.aggressive_revenue - rev.conservative_revenue
                efficiency = rev_lift / avg_reno_cost if avg_reno_cost > 0 else 0
                scores["renovation_efficiency"] = min(efficiency * 100, 100)
            else:
                scores["renovation_efficiency"] = 80  # No reno needed = good
        else:
            scores["renovation_efficiency"] = 50  # Unknown

        # 5. Market Strength
        market = result.market_metrics
        market_score = 50.0  # Base
        if market.occupancy_rate >= 0.70:
            market_score += 20
        elif market.occupancy_rate >= 0.55:
            market_score += 10
        if market.revenue_growth_yoy and market.revenue_growth_yoy > 0.05:
            market_score += 20
        elif market.revenue_growth_yoy and market.revenue_growth_yoy > 0:
            market_score += 10
        if market.revpar > 150:
            market_score += 10
        scores["market_strength"] = min(market_score, 100)

        # 6. Entry Price vs Purchase Comps
        if result.purchase_comps:
            adjusted_prices = [
                c.adjusted_price for c in result.purchase_comps if c.adjusted_price
            ]
            if adjusted_prices:
                median_comp = sorted(adjusted_prices)[len(adjusted_prices) // 2]
                price_ratio = result.property.list_price / median_comp if median_comp > 0 else 1
                # Below comps = good, above = bad
                if price_ratio <= 0.90:
                    scores["entry_price_vs_comps"] = 100
                elif price_ratio <= 0.95:
                    scores["entry_price_vs_comps"] = 80
                elif price_ratio <= 1.0:
                    scores["entry_price_vs_comps"] = 60
                elif price_ratio <= 1.05:
                    scores["entry_price_vs_comps"] = 40
                else:
                    scores["entry_price_vs_comps"] = 20
            else:
                scores["entry_price_vs_comps"] = 50
        else:
            scores["entry_price_vs_comps"] = 50

        # Weighted total
        total = (
            scores["cash_on_cash"] * self.weights.cash_on_cash
            + scores["cap_rate"] * self.weights.cap_rate
            + scores["revenue_upside"] * self.weights.revenue_upside
            + scores["renovation_efficiency"] * self.weights.renovation_efficiency
            + scores["market_strength"] * self.weights.market_strength
            + scores["entry_price_vs_comps"] * self.weights.entry_price_vs_comps
        )

        return round(max(0, min(100, total)), 1)

    def rank_properties(self, results: list[AnalysisResult]) -> list[AnalysisResult]:
        """Score all properties and sort by investment score descending."""
        for result in results:
            result.investment_score = self.score_property(result)

        results.sort(key=lambda r: r.investment_score, reverse=True)

        for i, result in enumerate(results, 1):
            result.investment_rank = i

        return results

    @staticmethod
    def _normalize_coc(coc: float) -> float:
        """Normalize cash-on-cash return to 0-100 score."""
        if coc >= 0.20:
            return 100
        elif coc >= 0.15:
            return 85
        elif coc >= 0.10:
            return 70
        elif coc >= 0.05:
            return 50
        elif coc >= 0.0:
            return 30
        else:
            return 10  # Negative CoC

    @staticmethod
    def _normalize_cap_rate(cap: float) -> float:
        """Normalize cap rate to 0-100 score."""
        if cap >= 0.10:
            return 100
        elif cap >= 0.08:
            return 85
        elif cap >= 0.06:
            return 70
        elif cap >= 0.04:
            return 50
        elif cap >= 0.02:
            return 30
        else:
            return 10
