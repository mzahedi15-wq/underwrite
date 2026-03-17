"""Market-level analysis - seasonality, supply/demand assessment."""

from __future__ import annotations

from str_researcher.models.str_performance import MarketMetrics
from str_researcher.utils.logging import get_logger

logger = get_logger("market")


class MarketAnalyzer:
    """Analyzes market-level STR data."""

    def calculate_seasonality(self, metrics: MarketMetrics) -> dict[int, float]:
        """Normalize seasonality index (1.0 = average month).

        If no AirDNA seasonality data is available, returns a moderate
        seasonal pattern as a default. The pattern is clearly logged so
        users know it's an estimate, not market-specific data.
        """
        if metrics.seasonality_index:
            return metrics.seasonality_index

        # Default seasonality when no data source provides monthly breakdowns.
        # This represents a typical US vacation-rental seasonal pattern.
        # The sensitivity analysis "Off-Peak" scenario will strip peak premiums
        # to show downside risk regardless of the seasonal pattern used.
        logger.info(
            "No monthly seasonality data available for %s — "
            "using generic seasonal pattern (sensitivity analysis will test off-peak scenarios)",
            metrics.market_name,
        )
        return {
            1: 0.70, 2: 0.75, 3: 0.90, 4: 1.00,
            5: 1.10, 6: 1.30, 7: 1.35, 8: 1.30,
            9: 1.05, 10: 1.10, 11: 0.80, 12: 0.85,
        }

    def supply_demand_assessment(self, metrics: MarketMetrics) -> str:
        """Evaluate market health and return a qualitative assessment."""
        growth = metrics.revenue_growth_yoy
        occupancy = metrics.occupancy_rate
        listing_count = metrics.active_listing_count

        signals = []

        # Occupancy health
        if occupancy >= 0.70:
            signals.append("Strong occupancy indicates healthy demand")
        elif occupancy >= 0.55:
            signals.append("Moderate occupancy — adequate demand")
        else:
            signals.append("Low occupancy may indicate oversupply")

        # Revenue growth
        if growth is not None:
            if growth > 0.05:
                signals.append(f"Revenue growing {growth:.0%} YoY — positive trend")
            elif growth > -0.05:
                signals.append("Revenue roughly flat YoY — stable market")
            else:
                signals.append(f"Revenue declining {growth:.0%} YoY — caution")

        # Supply context
        if listing_count > 0:
            if listing_count > 5000:
                signals.append(f"Large market ({listing_count:,} listings) — competitive")
            elif listing_count > 1000:
                signals.append(f"Mid-size market ({listing_count:,} listings)")
            else:
                signals.append(f"Small market ({listing_count:,} listings) — less competition")

        # RevPAR context
        if metrics.revpar > 0:
            if metrics.revpar > 200:
                signals.append(f"High RevPAR (${metrics.revpar:.0f}) — premium market")
            elif metrics.revpar > 100:
                signals.append(f"Moderate RevPAR (${metrics.revpar:.0f})")
            else:
                signals.append(f"Lower RevPAR (${metrics.revpar:.0f}) — value market")

        return " | ".join(signals)
