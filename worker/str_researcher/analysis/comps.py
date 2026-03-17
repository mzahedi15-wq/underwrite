"""Comparable property analysis - ranking, amenity matrix, purchase comp adjustments."""

from __future__ import annotations

import statistics
from typing import Optional

from str_researcher.models.comp import AmenityMatrix, PurchaseComp, STRComp
from str_researcher.models.property import PropertyListing
from str_researcher.utils.logging import get_logger

logger = get_logger("comps")


class CompAnalyzer:
    """Analyzes comparable properties for STR investment decisions."""

    def __init__(self, top_percentile: float = 0.90):
        self.top_percentile = top_percentile

    def rank_str_comps(self, comps: list[STRComp]) -> list[STRComp]:
        """Rank STR comps by performance score and flag top performers."""
        if not comps:
            return []

        # Sort by performance score (revenue * quality)
        sorted_comps = sorted(comps, key=lambda c: c.performance_score, reverse=True)

        # Mark top performers
        cutoff_idx = max(1, int(len(sorted_comps) * (1 - self.top_percentile)))
        for i, comp in enumerate(sorted_comps):
            comp.is_top_performer = i < cutoff_idx

        return sorted_comps

    def get_top_10_pct_revenue(self, comps: list[STRComp]) -> Optional[float]:
        """Get the median revenue of top 10% performers."""
        top = [c for c in comps if c.is_top_performer and c.annual_revenue_est]
        if not top:
            return None
        return statistics.median([c.annual_revenue_est for c in top])

    def build_amenity_matrix(self, comps: list[STRComp]) -> list[AmenityMatrix]:
        """Cross-tabulate amenity prevalence in top performers vs all comps."""
        if not comps:
            return []

        all_amenities: set[str] = set()
        for comp in comps:
            all_amenities.update(a.lower().strip() for a in comp.amenities if a)

        top_comps = [c for c in comps if c.is_top_performer]
        total = len(comps)
        total_top = len(top_comps) or 1

        matrix = []
        for amenity in sorted(all_amenities):
            count_all = sum(
                1 for c in comps if amenity in [a.lower().strip() for a in c.amenities]
            )
            count_top = sum(
                1
                for c in top_comps
                if amenity in [a.lower().strip() for a in c.amenities]
            )

            matrix.append(
                AmenityMatrix(
                    amenity_name=amenity,
                    count_in_top_10_pct=count_top,
                    count_in_all_comps=count_all,
                    prevalence_top_pct=count_top / total_top,
                    prevalence_all_pct=count_all / total if total > 0 else 0,
                )
            )

        # Sort by differentiator strength
        matrix.sort(
            key=lambda a: a.prevalence_top_pct - a.prevalence_all_pct, reverse=True
        )

        return matrix

    def adjust_purchase_comps(
        self,
        subject: PropertyListing,
        comps: list[PurchaseComp],
    ) -> list[PurchaseComp]:
        """Apply standard adjustments to purchase comps relative to subject property."""
        if not comps:
            return []

        for comp in comps:
            adjustments: dict[str, float] = {}

            # Bedroom adjustment: ~$15,000 per bedroom difference
            bed_diff = subject.beds - comp.beds
            if bed_diff != 0:
                adjustments["bed_diff"] = bed_diff * 15000

            # Bathroom adjustment: ~$8,000 per bathroom difference
            bath_diff = subject.baths - comp.baths
            if bath_diff != 0:
                adjustments["bath_diff"] = bath_diff * 8000

            # Sqft adjustment: use median $/sqft from comps
            if subject.sqft and comp.sqft and comp.sqft > 0:
                sqft_diff = subject.sqft - comp.sqft
                price_per_sqft = comp.sale_price / comp.sqft
                # Adjust at 50% of the raw $/sqft rate (diminishing returns)
                adjustments["sqft_diff"] = sqft_diff * price_per_sqft * 0.5

            # Age adjustment: ~$500 per year newer (rough)
            if subject.year_built and comp.sqft:
                # Approximate year built for comp
                adjustments["age_diff"] = 0  # Skip without comp year data

            # Distance adjustment: slight premium for closer properties
            # (no adjustment — distance is for relevance filtering, not price)

            comp.adjustments = adjustments
            comp.apply_adjustments()

        # Sort by distance (most comparable first)
        comps.sort(key=lambda c: c.distance_miles)

        return comps

    def estimate_arv(self, comps: list[PurchaseComp]) -> Optional[float]:
        """Estimate after-repair value from adjusted comp average."""
        adjusted = [c.adjusted_price for c in comps if c.adjusted_price]
        if not adjusted:
            return None
        return statistics.median(adjusted)
