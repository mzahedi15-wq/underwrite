"""
Underwrite Analysis Pipeline
Uses the full STR Researcher engine adapted for single-property analysis.
"""

from __future__ import annotations

import os
import statistics
from pathlib import Path
from typing import Optional

from str_researcher.analysis.ai_analyst import AIAnalyst
from str_researcher.analysis.comps import CompAnalyzer
from str_researcher.analysis.financial import FinancialAnalyzer
from str_researcher.analysis.revenue import RevenueEstimator
from str_researcher.analysis.scoring import InvestmentScorer
from str_researcher.config import (
    CostAssumptions,
    FinancingConfig,
    RegionConfig,
    ScoringWeights,
)
from str_researcher.gathering.airbnb import AirbnbScraper
from str_researcher.gathering.browser import BrowserManager
from str_researcher.gathering.cache import ScraperCache
from str_researcher.gathering.redfin import RedfinScraper
from str_researcher.gathering.vrbo import VRBOScraper
from str_researcher.gathering.zillow import ZillowScraper
from str_researcher.models.comp import STRComp
from str_researcher.models.property import PropertyListing
from str_researcher.models.report import AnalysisResult
from str_researcher.models.str_performance import (
    DualRevenueEstimate,
    MarketMetrics,
)


async def run_analysis_pipeline(
    analysis_id: str,
    property_url: str,
    property_type: str,
    strategy: str,
    renovation_budget: Optional[int],
    notes: Optional[str],
) -> dict:
    print(f"[{analysis_id}] Starting pipeline for {property_url}")

    costs = CostAssumptions()
    financing = FinancingConfig()

    cache_path = Path(os.environ.get("CACHE_DIR", "/tmp")) / "str_cache.db"
    async with ScraperCache(db_path=cache_path, ttl_hours=24) as cache:
        async with BrowserManager() as browser:
            # ── Step 1: Scrape property listing ──────────────────────────
            print(f"[{analysis_id}] Step 1: Scraping property data")
            prop = await _scrape_property(browser, cache, property_url)
            if not prop:
                raise ValueError(f"Failed to scrape property data from: {property_url}")
            print(
                f"[{analysis_id}] Property: {prop.address}, {prop.city}, {prop.state} "
                f"— ${prop.list_price:,}, {prop.beds}bd/{prop.baths}ba"
            )

            # ── Step 2: Build region config from property lat/lng ─────────
            region = _build_region_config(prop)

            # ── Step 3: Scrape STR comps from Airbnb + VRBO ──────────────
            print(f"[{analysis_id}] Step 2: Pulling STR comps")
            str_comps = await _gather_str_comps(browser, cache, region)
            print(f"[{analysis_id}] Found {len(str_comps)} STR comps")

            # ── Step 4: Comp analysis & revenue estimation ────────────────
            print(f"[{analysis_id}] Step 3: Analyzing comps and estimating revenue")
            comp_analyzer = CompAnalyzer(top_percentile=0.90)
            ranked_comps = comp_analyzer.rank_str_comps(str_comps)
            amenity_matrix = comp_analyzer.build_amenity_matrix(ranked_comps)
            top_10_revenue = comp_analyzer.get_top_10_pct_revenue(ranked_comps)

            revenue_estimator = RevenueEstimator()
            comp_estimate = revenue_estimator.estimate_from_comps(prop, ranked_comps)

            market = _build_market_from_comps(ranked_comps, prop)

            if comp_estimate is None:
                print(f"[{analysis_id}] No close comp match — falling back to market estimate")
                comp_estimate = revenue_estimator.estimate_from_market(prop, market)

            dual_revenue = revenue_estimator.reconcile(None, comp_estimate, top_10_revenue)

            # ── Step 5: Financial analysis ────────────────────────────────
            print(f"[{analysis_id}] Step 4: Building financial model")
            financial = FinancialAnalyzer(costs, financing)
            investment_metrics = financial.build_all_scenarios(
                prop,
                dual_revenue,
                market,
                renovation_budget=float(renovation_budget) if renovation_budget else None,
            )

            # ── Step 6: Score ─────────────────────────────────────────────
            result = AnalysisResult(
                property=prop,
                revenue_estimate=dual_revenue,
                market_metrics=market,
                investment_metrics=investment_metrics,
                str_comps=ranked_comps,
            )
            scorer = InvestmentScorer(ScoringWeights())
            result.investment_score = scorer.score_property(result)

            # ── Step 7: AI analysis ───────────────────────────────────────
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if anthropic_key:
                print(f"[{analysis_id}] Step 5: AI — scope of work + narrative")
                try:
                    ai = AIAnalyst(anthropic_key)
                    top_comps = [c for c in ranked_comps if c.is_top_performer][:10]

                    result.scope_of_work = await ai.generate_scope_of_work(
                        prop, top_comps, amenity_matrix, market, dual_revenue
                    )

                    best_coc = max(
                        (m.cash_on_cash_return for m in investment_metrics.values()),
                        default=0,
                    )
                    best_cap = max(
                        (m.cap_rate for m in investment_metrics.values()),
                        default=0,
                    )
                    result.investment_narrative = await ai.generate_investment_narrative(
                        prop, dual_revenue, market, best_coc, best_cap, result.investment_score
                    )

                    # Re-run financials with actual scope budget if available
                    if result.scope_of_work and result.scope_of_work.total_budget_high > 0:
                        scope_budget = (
                            result.scope_of_work.total_budget_low
                            + result.scope_of_work.total_budget_high
                        ) / 2
                        result.investment_metrics = financial.build_all_scenarios(
                            prop, dual_revenue, market, renovation_budget=scope_budget
                        )
                        investment_metrics = result.investment_metrics
                        result.investment_score = scorer.score_property(result)

                except Exception as e:
                    print(f"[{analysis_id}] AI analysis error (non-fatal): {e}")

            print(
                f"[{analysis_id}] Pipeline complete. Score: {result.investment_score:.0f}/100"
            )
            return _map_to_db_format(result)


async def _scrape_property(
    browser: BrowserManager,
    cache: ScraperCache,
    url: str,
) -> Optional[PropertyListing]:
    """Scrape a single property detail page from Zillow or Redfin."""
    if "zillow.com" in url:
        scraper = ZillowScraper(browser, cache)
        return await scraper.scrape_detail_url(url)
    elif "redfin.com" in url:
        scraper = RedfinScraper(browser, cache)
        return await scraper.scrape_detail_url(url)
    else:
        raise ValueError(f"Unsupported listing URL (expected zillow.com or redfin.com): {url}")


def _build_region_config(prop: PropertyListing) -> RegionConfig:
    """Build a RegionConfig from a property's coordinates for comp scraping."""
    lat = prop.lat or 33.4484  # Phoenix fallback
    lng = prop.lng or -112.0740
    return RegionConfig(
        name=f"{prop.city}, {prop.state}" if prop.city and prop.state else "Unknown",
        center_lat=lat,
        center_lng=lng,
        radius_miles=5.0,
        min_beds=max(1, (prop.beds or 1) - 1),
        max_beds=min(10, (prop.beds or 3) + 2),
        min_price=0,
        max_price=5_000_000,
    )


async def _gather_str_comps(
    browser: BrowserManager,
    cache: ScraperCache,
    region: RegionConfig,
) -> list[STRComp]:
    """Scrape Airbnb and VRBO for STR comps near the subject property."""
    comps: list[STRComp] = []

    try:
        airbnb = AirbnbScraper(browser, cache)
        airbnb_comps = await airbnb.scrape(region)
        comps.extend(airbnb_comps)
        print(f"  Airbnb: {len(airbnb_comps)} comps")
    except Exception as e:
        print(f"  Airbnb scraping error (non-fatal): {e}")

    try:
        vrbo = VRBOScraper(browser, cache)
        vrbo_comps = await vrbo.scrape(region)
        comps.extend(vrbo_comps)
        print(f"  VRBO: {len(vrbo_comps)} comps")
    except Exception as e:
        print(f"  VRBO scraping error (non-fatal): {e}")

    return comps


def _build_market_from_comps(comps: list[STRComp], prop: PropertyListing) -> MarketMetrics:
    """Build a MarketMetrics object from scraped STR comps."""
    if not comps:
        beds = prop.beds or 3
        return MarketMetrics(
            market_id="fallback",
            market_name=f"{prop.city}, {prop.state}",
            adr=float(150 + beds * 40),
            occupancy_rate=0.65,
            revpar=float((150 + beds * 40) * 0.65),
            active_listing_count=0,
        )

    rates = [c.nightly_rate_avg for c in comps if c.nightly_rate_avg and c.nightly_rate_avg > 50]
    occs = [c.occupancy_rate for c in comps if c.occupancy_rate and c.occupancy_rate > 0.1]

    adr = statistics.median(rates) if rates else 180.0
    occ = statistics.median(occs) if occs else 0.65

    return MarketMetrics(
        market_id="comp_derived",
        market_name=f"{prop.city}, {prop.state}",
        adr=adr,
        occupancy_rate=occ,
        revpar=adr * occ,
        active_listing_count=len(comps),
    )


def _map_to_db_format(result: AnalysisResult) -> dict:
    """Map AnalysisResult to the flat + reportJson dict the DB/frontend expects."""
    prop = result.property
    rev = result.revenue_estimate
    metrics = result.investment_metrics

    conv = metrics.get("Conventional") or (next(iter(metrics.values())) if metrics else None)

    if conv:
        annual_expenses = conv.annual_expenses
        financing = conv.financing
        beo = conv.break_even_occupancy * 100
    else:
        annual_expenses = 0.0
        financing = None
        beo = 0.0

    base_rev = rev.moderate_revenue
    cons_rev = rev.conservative_revenue
    agg_rev = rev.aggressive_revenue

    # Scale variable expenses (~35% variable with revenue)
    fixed_exp = annual_expenses * 0.65
    var_exp = annual_expenses * 0.35

    def scale_exp(r: float) -> float:
        return fixed_exp + var_exp * (r / base_rev if base_rev > 0 else 1.0)

    cons_exp = scale_exp(cons_rev)
    agg_exp = scale_exp(agg_rev)

    noi_base = base_rev - annual_expenses
    noi_cons = cons_rev - cons_exp
    noi_agg = agg_rev - agg_exp

    annual_debt = (financing.monthly_payment * 12) if financing else 0.0
    total_cash = financing.total_cash_needed if financing else 1.0
    purchase_price = financing.purchase_price if financing else (prop.list_price or 1)

    def coc(noi: float) -> float:
        return ((noi - annual_debt) / total_cash * 100) if total_cash > 0 else 0.0

    def cap(noi: float) -> float:
        return (noi / purchase_price * 100) if purchase_price > 0 else 0.0

    def irr_est(coc_val: float) -> float:
        return coc_val + 2.5

    adr_base = rev.primary_adr
    adr_cons = rev.conservative_adr
    adr_agg = rev.aggressive_adr
    occ_base = rev.primary_occupancy * 100
    occ_cons = rev.conservative_occupancy * 100
    occ_agg = rev.aggressive_occupancy * 100

    coc_base = coc(noi_base)
    coc_cons = coc(noi_cons)
    coc_agg = coc(noi_agg)

    financial_model = {
        "gross_revenue_base": int(base_rev),
        "gross_revenue_conservative": int(cons_rev),
        "gross_revenue_optimistic": int(agg_rev),
        "operating_expenses_base": int(annual_expenses),
        "operating_expenses_conservative": int(cons_exp),
        "operating_expenses_optimistic": int(agg_exp),
        "noi_base": int(noi_base),
        "noi_conservative": int(noi_cons),
        "noi_optimistic": int(noi_agg),
        "coc_return_base": round(coc_base, 1),
        "coc_return_conservative": round(coc_cons, 1),
        "coc_return_optimistic": round(coc_agg, 1),
        "cap_rate_base": round(cap(noi_base), 1),
        "cap_rate_conservative": round(cap(noi_cons), 1),
        "cap_rate_optimistic": round(cap(noi_agg), 1),
        "irr_base": round(irr_est(coc_base), 1),
        "irr_conservative": round(irr_est(coc_cons), 1),
        "irr_optimistic": round(irr_est(coc_agg), 1),
        "adr_base": int(adr_base),
        "adr_conservative": int(adr_cons),
        "adr_optimistic": int(adr_agg),
        "occupancy_base": round(occ_base, 1),
        "occupancy_conservative": round(occ_cons, 1),
        "occupancy_optimistic": round(occ_agg, 1),
        "breakeven_occupancy": round(beo, 1),
        "down_payment_assumed": int(financing.down_payment) if financing else 0,
        "mortgage_rate_assumed": round(financing.interest_rate * 100, 2) if financing else 0,
        "mortgage_payment_monthly": int(financing.monthly_payment) if financing else 0,
        "assumptions": (
            f"Conventional 30-yr fixed at {financing.interest_rate*100:.1f}% with "
            f"{financing.down_payment/purchase_price*100:.0f}% down "
            f"(${financing.down_payment:,.0f}). "
            f"Revenue based on {len(result.str_comps)} STR comps in the area."
        ) if financing else "Default financing assumptions applied.",
    }

    renovation_scope: list[dict] = []
    if result.scope_of_work:
        priority_map = {"must_have": "high", "high_impact": "medium", "nice_to_have": "low"}
        for rec in result.scope_of_work.recommendations:
            avg_cost = (rec.estimated_cost_low + rec.estimated_cost_high) / 2
            renovation_scope.append({
                "category": rec.category,
                "item": rec.recommendation,
                "estimated_cost": int(avg_cost),
                "roi_impact": priority_map.get(rec.priority, "medium"),
                "notes": rec.reasoning,
            })

    comps_data = [c.model_dump(mode="json") for c in result.str_comps[:20]]

    verdict = _determine_verdict(coc_base, irr_est(coc_base))

    return {
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip": prop.zip_code,
        "listPrice": prop.list_price,
        "beds": prop.beds,
        "baths": prop.baths,
        "sqft": prop.sqft,
        "verdict": verdict,
        "projRevenue": int(base_rev),
        "cocReturn": round(coc_base, 1),
        "capRate": round(cap(noi_base), 1),
        "irr": round(irr_est(coc_base), 1),
        "occupancy": round(occ_base, 1),
        "noi": int(noi_base),
        "adr": int(adr_base),
        "reportJson": {
            "financialModel": financial_model,
            "marketNarrative": result.investment_narrative or "",
            "renovationScope": renovation_scope,
            "comps": comps_data,
            "property": prop.model_dump(mode="json"),
        },
    }


def _determine_verdict(coc: float, irr: float) -> str:
    if coc >= 14 and irr >= 16:
        return "STRONG_BUY"
    elif coc >= 10 and irr >= 12:
        return "BUY"
    elif coc >= 6:
        return "HOLD"
    else:
        return "PASS"
