"""Dual revenue estimation - AirDNA + Airbnb comp analysis reconciliation."""

from __future__ import annotations

import statistics
from typing import Optional

from str_researcher.models.comp import STRComp
from str_researcher.models.str_performance import (
    DualRevenueEstimate,
    MarketMetrics,
    STREstimate,
)
from str_researcher.models.property import PropertyListing
from str_researcher.utils.logging import get_logger

logger = get_logger("revenue")


class RevenueEstimator:
    """Estimates revenue using dual methods and reconciles results."""

    def __init__(
        self,
        airdna_weight: float = 0.50,
        comp_weight: float = 0.50,
        divergence_threshold: float = 0.20,
    ):
        self.airdna_weight = airdna_weight
        self.comp_weight = comp_weight
        self.divergence_threshold = divergence_threshold


    def estimate_from_comps(
        self,
        subject: PropertyListing,
        comps: list[STRComp],
    ) -> Optional[STREstimate]:
        """Estimate revenue from STR comp analysis.

        Uses all comparable STR listings in the same geographic market.
        Revenue is estimated from the broader market data, then adjusted
        for the subject property's bedroom count and amenity profile.

        STR comps compete on *experience offered* (location, amenities,
        guest appeal), not just bedroom count — so we use a wide comp set.
        """
        # Filter to relevant market comps
        comparable = self._filter_comparable(subject, comps)

        if len(comparable) < 3:
            logger.warning(
                "Only %d comparable listings found for %s",
                len(comparable),
                subject.address,
            )
            if not comparable:
                return None

        # Separate comps into "close match" (same ±1 bed) and "market" (all)
        # Note: comps with beds=0 (unparsed) are excluded from close-match
        close_match = [
            c for c in comparable
            if c.beds > 0 and abs(c.beds - subject.beds) <= 1
        ]
        known_bed_comps = [c for c in comparable if c.beds > 0]
        occupancies = []

        for comp in comparable:
            occ = comp.occupancy_est
            if occ and occ > 0:
                occupancies.append(occ)

        # ── Bedroom-based ADR multiplier (relative to ~2-bed baseline) ──
        # Used when comps lack bedroom data. Airbnb search results show a
        # mix of property sizes; the median ADR approximates a 2-bed baseline.
        _BED_MULTIPLIER = {
            0: 0.60, 1: 0.80, 2: 1.00, 3: 1.25,
            4: 1.50, 5: 1.75, 6: 2.00, 7: 2.20,
        }

        # Three-tier strategy for ADR estimation:
        #   1. Close-match comps (±1 bed with known beds) — best accuracy
        #   2. Known-bed comps with per-comp bed adjustment
        #   3. Market-level: all comps scaled by subject bedroom multiplier
        if len(close_match) >= 3:
            # Tier 1: enough comps with matching bedroom count
            adrs = [c.nightly_rate_avg for c in close_match]
            revenues = [c.annual_revenue_est for c in close_match
                        if c.annual_revenue_est and c.annual_revenue_est > 0]
            logger.debug(
                "Tier 1 (close-match): %d comps for %d-bed %s",
                len(close_match), subject.beds, subject.address,
            )
        elif len(known_bed_comps) >= 3:
            # Tier 2: some comps have bed data — adjust each by bed diff
            adrs = []
            revenues = []
            for comp in known_bed_comps:
                bed_diff = subject.beds - comp.beds
                bed_adjustment = 1.0 + (bed_diff * 0.15)
                adrs.append(comp.nightly_rate_avg * bed_adjustment)
                if comp.annual_revenue_est and comp.annual_revenue_est > 0:
                    revenues.append(comp.annual_revenue_est * bed_adjustment)
            logger.debug(
                "Tier 2 (known-bed comps): %d comps for %d-bed %s",
                len(known_bed_comps), subject.beds, subject.address,
            )
        else:
            # Tier 3: most/all comps lack bedroom data — scale market ADR
            # by the subject's bedroom count relative to a 2-bed baseline
            multiplier = _BED_MULTIPLIER.get(
                min(subject.beds, 7),
                1.0 + (subject.beds - 2) * 0.25,
            )
            adrs = [c.nightly_rate_avg * multiplier for c in comparable]
            revenues = [
                c.annual_revenue_est * multiplier for c in comparable
                if c.annual_revenue_est and c.annual_revenue_est > 0
            ]
            logger.info(
                "Tier 3 (market-level): %d comps × %.2f bed multiplier "
                "for %d-bed %s",
                len(comparable), multiplier, subject.beds, subject.address,
            )

        if not adrs:
            return None

        # Use median to reduce outlier impact
        median_adr = statistics.median(adrs)
        median_occ = statistics.median(occupancies) if occupancies else 0.65

        # Calculate estimated annual revenue
        if revenues:
            median_revenue = statistics.median(revenues)
        else:
            median_revenue = median_adr * 365 * median_occ

        # Adjust for amenity gaps
        adjustment = self._amenity_adjustment(subject, comparable)
        adjusted_revenue = median_revenue * adjustment

        return STREstimate(
            address=subject.address,
            annual_revenue=round(adjusted_revenue, 2),
            adr=round(median_adr, 2),
            occupancy_rate=round(median_occ, 4),
            source="comp_derived",
        )

    def reconcile(
        self,
        airdna_estimate: Optional[STREstimate],
        comp_estimate: Optional[STREstimate],
        top_10_pct_revenue: Optional[float] = None,
    ) -> DualRevenueEstimate:
        """Reconcile AirDNA and comp-based estimates into a DualRevenueEstimate."""
        result = DualRevenueEstimate(
            airdna_estimate=airdna_estimate,
            comp_estimate=comp_estimate,
        )

        airdna_rev = airdna_estimate.annual_revenue if airdna_estimate else 0
        comp_rev = comp_estimate.annual_revenue if comp_estimate else 0

        # Conservative = lower of the two (or the one available)
        if airdna_rev > 0 and comp_rev > 0:
            result.conservative_revenue = min(airdna_rev, comp_rev)
            result.moderate_revenue = (
                airdna_rev * self.airdna_weight + comp_rev * self.comp_weight
            )

            # Aggressive = higher of the two, or top 10% comp performance
            higher = max(airdna_rev, comp_rev)
            if top_10_pct_revenue and top_10_pct_revenue > higher:
                result.aggressive_revenue = top_10_pct_revenue
            else:
                result.aggressive_revenue = higher

            # Calculate divergence
            avg = (airdna_rev + comp_rev) / 2
            if avg > 0:
                result.divergence_pct = abs(airdna_rev - comp_rev) / avg
                result.needs_manual_review = (
                    result.divergence_pct > self.divergence_threshold
                )

        elif airdna_rev > 0:
            result.conservative_revenue = airdna_rev * 0.85
            result.moderate_revenue = airdna_rev
            result.aggressive_revenue = (
                top_10_pct_revenue
                if top_10_pct_revenue
                else airdna_rev * 1.15
            )

        elif comp_rev > 0:
            result.conservative_revenue = comp_rev * 0.85
            result.moderate_revenue = comp_rev
            result.aggressive_revenue = (
                top_10_pct_revenue
                if top_10_pct_revenue
                else comp_rev * 1.15
            )

        return result

    def _filter_comparable(
        self, subject: PropertyListing, comps: list[STRComp]
    ) -> list[STRComp]:
        """Filter comps to those in the same market experience.

        STR comps compete on *experience* (location, amenities, guest appeal),
        not just bedroom count.  All STR listings in the same geographic area
        are part of the competitive set.  We include all comps within range
        that have valid rate data, then sort by similarity so the most similar
        comps get the most weight.
        """
        comparable = []

        for comp in comps:
            # Must be within reasonable distance (15 miles)
            if comp.distance_miles > 15:
                continue

            # Must have a nightly rate
            if comp.nightly_rate_avg <= 0:
                continue

            comparable.append(comp)

        # Sort by relevance: closer bed count first, then closer distance
        # — but DO NOT filter by bed count
        comparable.sort(
            key=lambda c: abs(c.beds - subject.beds) * 5 + c.distance_miles
        )

        # Keep top 50 most relevant — larger pool for better estimates
        return comparable[:50]

    def estimate_from_market(
        self,
        subject: PropertyListing,
        market: MarketMetrics,
    ) -> STREstimate:
        """Fallback revenue estimate using market-level ADR and occupancy.

        Used when no STR comps are available (scrapers returned 0 comps).
        Adjusts market ADR by bedroom count — larger properties command higher
        nightly rates.
        """
        base_adr = market.adr
        occupancy = market.occupancy_rate

        # Adjust ADR by bedroom count relative to a 2-bed baseline
        bed_multiplier = {
            0: 0.60, 1: 0.80, 2: 1.00, 3: 1.25,
            4: 1.50, 5: 1.75, 6: 2.00, 7: 2.20,
        }
        multiplier = bed_multiplier.get(
            min(subject.beds, 7), 1.0 + (subject.beds - 2) * 0.25
        )

        adjusted_adr = base_adr * multiplier
        annual_revenue = adjusted_adr * 365 * occupancy

        logger.info(
            "Market-based estimate for %s: ADR $%.0f × %.0f%% occ = $%.0f/yr",
            subject.address, adjusted_adr, occupancy * 100, annual_revenue,
        )

        return STREstimate(
            address=subject.address,
            annual_revenue=round(annual_revenue, 2),
            adr=round(adjusted_adr, 2),
            occupancy_rate=round(occupancy, 4),
            source="comp_derived",
        )

    @staticmethod
    def _amenity_adjustment(
        subject: PropertyListing, comps: list[STRComp]
    ) -> float:
        """Calculate an adjustment factor based on likely amenity gaps.

        Since we don't know the subject's amenities before purchase,
        we apply a slight discount assuming some amenity investment needed.
        """
        # Count premium amenities in comps
        premium_amenities = [
            "hot tub", "pool", "game room", "sauna", "theater",
            "fire pit", "ev charger", "gym", "mountain view", "lake view",
        ]

        premium_count = 0
        total_comps = len(comps)

        for comp in comps:
            amenities_lower = [a.lower() for a in comp.amenities]
            for pa in premium_amenities:
                if any(pa in a for a in amenities_lower):
                    premium_count += 1
                    break

        if total_comps == 0:
            return 0.95  # Default slight discount

        premium_rate = premium_count / total_comps

        # If most comps have premium amenities, apply a discount
        # since the subject probably needs investment
        if premium_rate > 0.7:
            return 0.85  # 15% discount — needs significant amenity investment
        elif premium_rate > 0.4:
            return 0.92  # 8% discount
        else:
            return 0.97  # 3% discount — market doesn't require many premiums
