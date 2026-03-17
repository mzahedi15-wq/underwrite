"""Pipeline orchestrator — gather, analyze, score, report."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from str_researcher.analysis.ai_analyst import AIAnalyst
from str_researcher.analysis.comps import CompAnalyzer
from str_researcher.analysis.financial import FinancialAnalyzer
from str_researcher.analysis.market import MarketAnalyzer
from str_researcher.analysis.marketing import MarketingPlanGenerator
from str_researcher.analysis.revenue import RevenueEstimator
from str_researcher.analysis.scoring import InvestmentScorer
from str_researcher.config import AppConfig
from str_researcher.gathering.airdna import AirDNAClient
from str_researcher.gathering.airbnb import AirbnbScraper
from str_researcher.gathering.browser import BrowserManager
from str_researcher.gathering.cache import ScraperCache
from str_researcher.gathering.redfin import RedfinScraper
from str_researcher.gathering.vrbo import VRBOScraper
from str_researcher.gathering.zillow import ZillowScraper
from str_researcher.models.property import PropertyListing
from str_researcher.models.report import AnalysisResult
from str_researcher.models.str_performance import DualRevenueEstimate, MarketMetrics
from str_researcher.reporting.docs import DocsBuilder
from str_researcher.reporting.google_auth import GoogleAuthManager
from str_researcher.reporting.sheets import SheetsBuilder
from str_researcher.utils.geocoding import are_same_property
from str_researcher.utils.logging import get_logger

logger = get_logger("pipeline")

# Type for progress callback: (step_number, total_steps, message)
ProgressCallback = Callable[[int, int, str], None]


class AnalysisPipeline:
    """Orchestrates the full STR investment analysis pipeline."""

    TOTAL_STEPS = 10

    def __init__(self, config: AppConfig):
        self.config = config

    async def run(
        self,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> list[AnalysisResult]:
        """Run the full analysis pipeline.

        Returns a list of AnalysisResult sorted by investment score (best first).
        """

        def _progress(step: int, msg: str) -> None:
            if progress_cb:
                progress_cb(step, self.TOTAL_STEPS, msg)
            logger.info("[Step %d/%d] %s", step, self.TOTAL_STEPS, msg)

        region = self.config.region
        api_keys = self.config.api_keys

        # Use cache as a context manager for the entire pipeline run
        async with ScraperCache(ttl_hours=self.config.cache_ttl_hours) as cache:
            # ── Step 1: Initialize ──
            _progress(1, "Loading configuration and initializing services...")

            # ── Step 2: Market Context ──
            has_airdna = bool(api_keys.airdna_api_key and api_keys.airdna_api_key != "your_airdna_api_key_here")
            if has_airdna:
                _progress(2, "Fetching market data from AirDNA...")
            else:
                _progress(2, "No AirDNA key — market data will be derived from STR comps...")
            market = await self._get_market_context(api_keys.airdna_api_key, region, cache)
            if market.market_id == "pending_comps":
                _progress(2, "Market data pending — will compute from Airbnb/VRBO comps")
            else:
                _progress(2, f"Market data ready (AirDNA) — ADR ${market.adr:.0f}, Occupancy {market.occupancy_rate:.0%}")

            # ── Step 3: Gather Listings ──
            _progress(3, "Scraping property listings from Zillow and Redfin (1-3 min)...")
            listings = await self._gather_listings(region, cache)

            if not listings:
                logger.error("No listings found for region %s", region.name)
                return []

            listings = listings[: self.config.max_listings_to_analyze]
            _progress(3, f"Found {len(listings)} listings for analysis")

            # ── Step 4: Revenue Estimation (AirDNA — optional) ──
            airdna_estimates: dict = {}
            if has_airdna:
                _progress(4, f"Estimating revenue for {len(listings)} properties via AirDNA (2-5 min)...")
                airdna = AirDNAClient(api_keys.airdna_api_key, cache=cache)
                airdna_estimates = await airdna.bulk_rentalizer(listings)
                airdna_ok = sum(1 for v in airdna_estimates.values() if v is not None)
                _progress(4, f"AirDNA complete — {airdna_ok}/{len(listings)} estimates received")
            else:
                _progress(4, "Skipping AirDNA (no API key) — revenue will come from Airbnb/VRBO comps")

            # ── Step 5: Gather STR Comps ──
            _progress(5, "Scraping STR comps from Airbnb and VRBO (2-5 min)...")
            str_comps = await self._gather_str_comps(region, cache)
            _progress(5, f"Found {len(str_comps)} STR comps")

            # ── Step 5b: Refine market data from comps (if needed) ──
            if market.market_id == "pending_comps":
                market = self._refine_market_from_comps(market, str_comps)
                source_label = "comp-derived" if market.market_id == "comp_derived" else "fallback"
                _progress(5, f"Market data ({source_label}) — ADR ${market.adr:.0f}, Occupancy {market.occupancy_rate:.0%}")

            # ── Step 6: Analyze Comps & Revenue ──
            _progress(6, "Analyzing comps and building revenue estimates...")
            comp_analyzer = CompAnalyzer(top_percentile=self.config.top_performer_percentile)
            ranked_comps = comp_analyzer.rank_str_comps(str_comps)
            amenity_matrix = comp_analyzer.build_amenity_matrix(ranked_comps)
            top_10_revenue = comp_analyzer.get_top_10_pct_revenue(ranked_comps)

            revenue_estimator = RevenueEstimator(
                airdna_weight=self.config.revenue_blend_airdna_weight,
                comp_weight=self.config.revenue_blend_comp_weight,
            )
            n_top = sum(1 for c in ranked_comps if c.is_top_performer)
            _progress(6, f"Comp analysis done — {len(ranked_comps)} ranked, {n_top} top performers")

            # ── Step 7: Financial Analysis ──
            _progress(7, "Fetching purchase comps and running financial models (1-2 min)...")
            financial = FinancialAnalyzer(self.config.costs, self.config.financing)
            market_analyzer = MarketAnalyzer()

            if not market.seasonality_index:
                market.seasonality_index = market_analyzer.calculate_seasonality(market)

            purchase_comps = await self._gather_purchase_comps(region, cache)
            _progress(7, f"Found {len(purchase_comps)} purchase comps — modeling {len(listings)} properties...")

            results: list[AnalysisResult] = []
            fallback_count = 0
            for i, listing in enumerate(listings):
                comp_estimate = revenue_estimator.estimate_from_comps(listing, ranked_comps)

                # If no comp-based estimate (e.g., no STR comps found),
                # fall back to market-level data so revenue is never $0
                if comp_estimate is None:
                    comp_estimate = revenue_estimator.estimate_from_market(listing, market)
                    fallback_count += 1

                airdna_est = airdna_estimates.get(listing.address)
                dual_revenue = revenue_estimator.reconcile(
                    airdna_est, comp_estimate, top_10_revenue
                )
                comps_copy = [c.model_copy(deep=True) for c in purchase_comps]
                adjusted_comps = comp_analyzer.adjust_purchase_comps(listing, comps_copy)
                investment_metrics = financial.build_all_scenarios(
                    listing, dual_revenue, market,
                    purchase_comps=adjusted_comps,
                )

                results.append(AnalysisResult(
                    property=listing,
                    revenue_estimate=dual_revenue,
                    market_metrics=market,
                    investment_metrics=investment_metrics,
                    purchase_comps=adjusted_comps,
                    str_comps=ranked_comps,
                ))

                if (i + 1) % 10 == 0 or i + 1 == len(listings):
                    _progress(7, f"Financial modeling: {i + 1}/{len(listings)} properties done")

            if fallback_count > 0:
                _progress(7, f"Note: {fallback_count}/{len(listings)} properties used market-data revenue estimates (no STR comps matched)")

            # ── Step 8: Score & Rank ──
            _progress(8, "Scoring and ranking all properties...")
            scorer = InvestmentScorer(self.config.scoring_weights)
            results = scorer.rank_properties(results)
            if results:
                best = results[0]
                _progress(8, f"Top property: {best.property.address} (score {best.investment_score:.0f}/100)")

            # ── Step 9: AI Analysis (top N) ──
            top_n = self.config.top_n_for_full_reports
            top_results = results[:top_n]

            if api_keys.anthropic_api_key:
                _progress(9, f"Generating AI analysis for top {len(top_results)} properties (1-3 min)...")
                ai_analyst = AIAnalyst(api_keys.anthropic_api_key)
                marketing_gen = MarketingPlanGenerator(api_keys.anthropic_api_key)

                for idx, result in enumerate(top_results):
                    addr_short = result.property.address[:40]
                    _progress(9, f"AI analysis: {idx + 1}/{len(top_results)} — {addr_short}...")
                    try:
                        top_comps = [c for c in ranked_comps if c.is_top_performer][:10]

                        result.scope_of_work = await ai_analyst.generate_scope_of_work(
                            result.property, top_comps, amenity_matrix,
                            market, result.revenue_estimate,
                        )

                        best_coc = max(
                            (m.cash_on_cash_return for m in result.investment_metrics.values()),
                            default=0,
                        )
                        best_cap = max(
                            (m.cap_rate for m in result.investment_metrics.values()),
                            default=0,
                        )
                        result.investment_narrative = await ai_analyst.generate_investment_narrative(
                            result.property, result.revenue_estimate, market,
                            best_coc, best_cap, result.investment_score,
                        )

                        result.marketing_plan = await marketing_gen.generate_marketing_plan(
                            result.property, top_comps, market,
                            result.revenue_estimate, result.scope_of_work,
                        )

                        # Re-run financial analysis using the scope's actual
                        # renovation budget instead of the flat per-bed estimate
                        if (result.scope_of_work
                                and result.scope_of_work.total_budget_high > 0):
                            scope_budget = (
                                result.scope_of_work.total_budget_low
                                + result.scope_of_work.total_budget_high
                            ) / 2  # midpoint
                            _progress(
                                9,
                                f"  Updating financials with scope budget "
                                f"${scope_budget:,.0f}...",
                            )
                            result.investment_metrics = financial.build_all_scenarios(
                                result.property,
                                result.revenue_estimate,
                                market,
                                renovation_budget=scope_budget,
                                purchase_comps=result.purchase_comps,
                            )

                    except Exception as e:
                        logger.error("AI analysis failed for %s: %s", result.property.address, e)

                # Re-score after financial refresh so ranks reflect scope costs
                results = scorer.rank_properties(results)

            else:
                _progress(9, "No Anthropic API key — skipping AI analysis")

            # ── Step 10: Generate Reports ──
            _progress(10, "Generating Google Sheets and Docs reports (1-2 min)...")
            try:
                await self._generate_reports(results, top_results)
                _progress(10, "Reports generated successfully")
            except Exception as e:
                logger.error("Report generation failed: %s", e)
                _progress(10, f"Report generation skipped — {e}")

        logger.info(
            "Pipeline complete: %d properties analyzed, top %d with full reports",
            len(results), len(top_results),
        )
        return results

    # ── Private Pipeline Steps ──

    async def _get_market_context(
        self, airdna_key: str, region, cache: ScraperCache,
    ) -> MarketMetrics:
        """Fetch market-level data from AirDNA.

        Returns a placeholder if no AirDNA key is available.
        The placeholder will be replaced with comp-derived data after
        STR comps are scraped (see _refine_market_from_comps).
        """
        if not airdna_key or airdna_key == "your_airdna_api_key_here":
            logger.warning(
                "No AirDNA key — using placeholder market data "
                "(will be updated from STR comps)"
            )
            return MarketMetrics(
                market_id="pending_comps",
                market_name=region.name,
                adr=0.0,
                occupancy_rate=0.0,
                revpar=0.0,
            )

        airdna = AirDNAClient(airdna_key, cache=cache)
        try:
            market_info = await airdna.search_market(region.name)
            if market_info:
                market_id = str(market_info.get("id", ""))
                if not market_id:
                    # Try alternative key names
                    market_id = str(
                        market_info.get("market_id", "")
                        or market_info.get("marketId", "")
                    )
                if market_id:
                    metrics = await airdna.market_metrics(market_id)
                    if metrics:
                        return metrics
        except Exception as e:
            logger.error("Failed to get market data: %s", e)

        return MarketMetrics(
            market_id="pending_comps",
            market_name=region.name,
            adr=0.0,
            occupancy_rate=0.0,
            revpar=0.0,
        )

    def _refine_market_from_comps(
        self, market: MarketMetrics, str_comps: list,
    ) -> MarketMetrics:
        """Derive real market-level metrics from scraped STR comp data.

        Called after Step 5 (STR comp gathering) to replace placeholder
        market data with actual values computed from Airbnb/VRBO comps.
        If AirDNA already provided real data (market_id is not 'pending_comps'),
        this is a no-op.
        """
        import statistics as _stats

        # If we already have real AirDNA data, don't overwrite
        if market.market_id not in ("pending_comps", "unknown"):
            logger.debug(
                "Market data already sourced from AirDNA — skipping comp refinement"
            )
            return market

        if not str_comps:
            logger.warning(
                "No STR comps available to derive market data — "
                "using conservative defaults"
            )
            # Last-resort defaults when we have neither AirDNA nor comps
            market.market_id = "default_fallback"
            market.adr = 150.0
            market.occupancy_rate = 0.55
            market.revpar = 82.5
            return market

        # ── Compute ADR from comp nightly rates ──
        nightly_rates = [
            c.nightly_rate_avg for c in str_comps
            if hasattr(c, 'nightly_rate_avg') and c.nightly_rate_avg > 0
        ]

        # ── Compute occupancy from comp occupancy estimates ──
        occupancies = [
            c.occupancy_est for c in str_comps
            if hasattr(c, 'occupancy_est') and c.occupancy_est
            and c.occupancy_est > 0
        ]

        # ── Compute annual revenue from comp revenue estimates ──
        revenues = [
            c.annual_revenue_est for c in str_comps
            if hasattr(c, 'annual_revenue_est') and c.annual_revenue_est
            and c.annual_revenue_est > 0
        ]

        if nightly_rates:
            market.adr = round(_stats.median(nightly_rates), 2)
        else:
            # Shouldn't happen if comps exist, but fallback
            market.adr = 150.0

        if occupancies:
            market.occupancy_rate = round(_stats.median(occupancies), 4)
        else:
            # If no occupancy data on comps, estimate from revenue/ADR
            if revenues and market.adr > 0:
                median_rev = _stats.median(revenues)
                implied_occ = median_rev / (market.adr * 365)
                market.occupancy_rate = round(min(implied_occ, 0.95), 4)
            else:
                market.occupancy_rate = 0.60  # conservative default

        market.revpar = round(market.adr * market.occupancy_rate, 2)
        market.active_listing_count = len(str_comps)
        market.market_id = "comp_derived"

        logger.info(
            "Market data derived from %d STR comps: "
            "ADR $%.0f, Occupancy %.0f%%, RevPAR $%.0f",
            len(str_comps),
            market.adr,
            market.occupancy_rate * 100,
            market.revpar,
        )

        return market

    async def _gather_listings(
        self, region, cache: ScraperCache,
    ) -> list[PropertyListing]:
        """Scrape listings from Zillow and Redfin, deduplicate."""
        all_listings: list[PropertyListing] = []

        async with BrowserManager(
            proxy_url=self.config.api_keys.proxy_url
        ) as browser:
            tasks = []

            # Always try both scrapers — they work without explicit URLs
            redfin = RedfinScraper(browser, cache)
            tasks.append(redfin.scrape(region))

            zillow = ZillowScraper(browser, cache)
            tasks.append(zillow.scrape(region))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Scraper failed: %s", result)
                elif isinstance(result, list):
                    all_listings.extend(result)

        # Deduplicate
        unique: list[PropertyListing] = []
        for listing in all_listings:
            is_dup = False
            for existing in unique:
                if are_same_property(
                    listing.address, listing.lat, listing.lng,
                    existing.address, existing.lat, existing.lng,
                    listing.beds, existing.beds,
                ):
                    is_dup = True
                    break
            if not is_dup:
                unique.append(listing)

        return unique

    async def _gather_str_comps(self, region, cache: ScraperCache) -> list:
        """Scrape STR comp listings from Airbnb and VRBO."""
        from str_researcher.models.comp import STRComp

        all_comps: list[STRComp] = []

        async with BrowserManager(
            proxy_url=self.config.api_keys.proxy_url
        ) as browser:
            tasks = []

            airbnb = AirbnbScraper(browser, cache)
            tasks.append(airbnb.scrape(region))

            vrbo = VRBOScraper(browser, cache)
            tasks.append(vrbo.scrape(region))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("STR comp scraper failed: %s", result)
                elif isinstance(result, list):
                    all_comps.extend(result)

        logger.info("Gathered %d STR comps total", len(all_comps))
        return all_comps

    async def _gather_purchase_comps(
        self, region, cache: ScraperCache,
    ) -> list:
        """Scrape recently sold comps for the region."""
        try:
            async with BrowserManager(
                proxy_url=self.config.api_keys.proxy_url
            ) as browser:
                redfin = RedfinScraper(browser, cache)
                comps = await redfin.scrape_purchase_comps(region)
                return comps
        except Exception as e:
            logger.error("Failed to get purchase comps: %s", e)
            return []

    async def _generate_reports(
        self, all_results: list[AnalysisResult], top_results: list[AnalysisResult]
    ) -> None:
        """Generate Google Sheets and Docs reports."""
        creds_path = self.config.api_keys.google_credentials_path

        try:
            auth = GoogleAuthManager(creds_path)
            # interactive=False — never open browser popup from background thread
            auth.authenticate(interactive=False)
        except Exception as e:
            logger.error("Google auth failed — skipping report generation: %s", e)
            return

        # Google Sheets
        gc = auth.get_gspread_client()
        sheets = SheetsBuilder(gc)

        # Per-property sheets (top N)
        for result in top_results:
            try:
                result.sheet_url = sheets.create_property_sheet(result)
            except Exception as e:
                logger.error("Failed to create sheet for %s: %s", result.property.address, e)

        # Master ranking sheet
        try:
            ranking_url = sheets.create_master_ranking(all_results)
            logger.info("Master ranking sheet: %s", ranking_url)
        except Exception as e:
            logger.error("Failed to create ranking sheet: %s", e)

        # Google Docs (scope of work + marketing plan for top N)
        try:
            docs_service = auth.get_docs_service()
            drive_service = auth.get_drive_service()
            docs = DocsBuilder(docs_service, drive_service)

            for result in top_results:
                try:
                    if result.scope_of_work:
                        result.scope_doc_url = docs.create_scope_of_work_doc(result)
                except Exception as e:
                    logger.error("Failed to create scope doc for %s: %s", result.property.address, e)

                try:
                    if result.marketing_plan:
                        result.marketing_doc_url = docs.create_marketing_plan_doc(result)
                except Exception as e:
                    logger.error("Failed to create marketing doc for %s: %s", result.property.address, e)
        except Exception as e:
            logger.error("Failed to initialize Google Docs: %s", e)
