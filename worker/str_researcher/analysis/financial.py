"""Financial analysis engine for STR investments."""

from __future__ import annotations

from typing import Optional

from str_researcher.config import CostAssumptions, FinancingConfig
from str_researcher.models.comp import PurchaseComp
from str_researcher.models.financials import (
    FinancingScenario,
    InvestmentMetrics,
    MonthlyCashflow,
    SensitivityAnalysis,
    SensitivityCase,
    SuggestedOffer,
)
from str_researcher.models.property import PropertyListing
from str_researcher.models.str_performance import DualRevenueEstimate, MarketMetrics


class FinancialAnalyzer:
    """Performs all financial calculations for STR investment analysis."""

    def __init__(self, costs: CostAssumptions, financing: FinancingConfig):
        self.costs = costs
        self.financing = financing

    def build_all_scenarios(
        self,
        prop: PropertyListing,
        revenue: DualRevenueEstimate,
        market: MarketMetrics,
        renovation_budget: float | None = None,
        purchase_comps: Optional[list[PurchaseComp]] = None,
    ) -> dict[str, InvestmentMetrics]:
        """Build financial models for all financing scenarios.

        Parameters
        ----------
        renovation_budget : float, optional
            If provided, replaces the default flat ``furnishing_per_bed``
            estimate with the actual renovation/furnishing budget (typically
            from the AI-generated Scope of Work).
        purchase_comps : list[PurchaseComp], optional
            Recently sold comparable properties used for offer calculation.
        """
        scenarios = {}
        annual_revenue = revenue.moderate_revenue

        # Calculate suggested offer once (shared across scenarios)
        offer = self._calculate_suggested_offer(
            prop, revenue, market, purchase_comps,
        )

        for name in ["Conventional", "DSCR", "Cash"]:
            scenario = self._build_financing_scenario(
                name, prop, renovation_budget=renovation_budget,
            )
            metrics = self._calculate_metrics(
                prop, scenario, annual_revenue, market
            )
            # Attach sensitivity analysis
            metrics.sensitivity = self._build_sensitivity_analysis(
                prop, scenario, annual_revenue, market, metrics
            )
            # Attach suggested offer
            metrics.suggested_offer = offer
            scenarios[name] = metrics

        return scenarios

    def _build_financing_scenario(
        self,
        name: str,
        prop: PropertyListing,
        renovation_budget: float | None = None,
    ) -> FinancingScenario:
        """Build a financing scenario.

        If *renovation_budget* is given it replaces the default
        ``furnishing_per_bed × beds`` startup cost.
        """
        price = prop.list_price
        furnishing = (
            renovation_budget
            if renovation_budget is not None
            else self.costs.furnishing_per_bed * prop.beds
        )

        if name == "Cash":
            closing = price * self.financing.closing_cost_pct
            return FinancingScenario(
                name="Cash",
                purchase_price=price,
                down_payment=float(price),
                loan_amount=0.0,
                interest_rate=0.0,
                monthly_payment=0.0,
                closing_costs=closing,
                renovation_furnishing=furnishing,
                total_cash_needed=float(price) + closing + furnishing,
            )

        if name == "Conventional":
            down_pct = self.financing.conventional_down_pct
            rate = self.financing.conventional_rate
            term = self.financing.conventional_term_years
        else:  # DSCR
            down_pct = self.financing.dscr_down_pct
            rate = self.financing.dscr_rate
            term = self.financing.dscr_term_years

        down = price * down_pct
        loan = price - down
        monthly_pmt = self._monthly_mortgage(loan, rate, term)
        closing = price * self.financing.closing_cost_pct

        return FinancingScenario(
            name=name,
            purchase_price=price,
            down_payment=down,
            loan_amount=loan,
            interest_rate=rate,
            monthly_payment=monthly_pmt,
            closing_costs=closing,
            renovation_furnishing=furnishing,
            total_cash_needed=down + closing + furnishing,
        )

    def _calculate_metrics(
        self,
        prop: PropertyListing,
        scenario: FinancingScenario,
        annual_revenue: float,
        market: MarketMetrics,
    ) -> InvestmentMetrics:
        """Calculate all investment metrics for a scenario."""
        # Build monthly cashflows
        monthly_cashflows = self._build_monthly_cashflows(
            annual_revenue, scenario, market
        )

        # Annual totals
        annual_gross = sum(m.gross_revenue for m in monthly_cashflows)
        annual_expenses = sum(m.total_expenses for m in monthly_cashflows)
        annual_net = sum(m.net_cashflow for m in monthly_cashflows)

        # NOI (before debt service)
        annual_operating_expenses = annual_expenses - (scenario.monthly_payment * 12)
        noi = annual_gross - annual_operating_expenses

        # Key metrics
        cap_rate = noi / prop.list_price if prop.list_price > 0 else 0
        coc = (
            annual_net / scenario.total_cash_needed
            if scenario.total_cash_needed > 0
            else 0
        )
        annual_debt_service = scenario.monthly_payment * 12
        dscr = noi / annual_debt_service if annual_debt_service > 0 else None

        # Break-even occupancy
        break_even = self._break_even_occupancy(
            annual_operating_expenses + annual_debt_service,
            annual_revenue,
        )

        return InvestmentMetrics(
            annual_gross_revenue=annual_gross,
            annual_expenses=annual_expenses,
            noi=noi,
            cap_rate=cap_rate,
            cash_on_cash_return=coc,
            dscr=dscr,
            break_even_occupancy=break_even,
            monthly_cashflows=monthly_cashflows,
            financing=scenario,
            annual_net_cashflow=annual_net,
        )

    def _build_monthly_cashflows(
        self,
        annual_revenue: float,
        scenario: FinancingScenario,
        market: MarketMetrics,
    ) -> list[MonthlyCashflow]:
        """Build 12-month cashflow projection with seasonality."""
        cashflows = []
        monthly_base = annual_revenue / 12

        for month in range(1, 13):
            # Apply seasonality
            season_factor = market.seasonality_index.get(month, 1.0)
            gross = monthly_base * season_factor

            # Variable costs
            mgmt_fee = gross * self.costs.management_fee_pct
            platform_fee = gross * self.costs.platform_fee_pct
            maintenance = gross * self.costs.maintenance_pct

            # Estimate cleaning based on occupancy-implied turns
            avg_stay = 3.5  # Average stay length in nights
            if market.occupancy_rate > 0:
                occupied_nights = 30 * market.occupancy_rate * season_factor
            else:
                occupied_nights = 30 * 0.65 * season_factor
            turns = occupied_nights / avg_stay
            cleaning = turns * self.costs.cleaning_per_turn

            # Fixed costs
            mortgage = scenario.monthly_payment
            taxes = (scenario.purchase_price * self.costs.property_tax_rate) / 12
            insurance = self.costs.insurance_annual / 12
            hoa = self.costs.hoa_monthly
            utilities = self.costs.utilities_monthly

            total_exp = (
                mgmt_fee + cleaning + platform_fee + mortgage
                + taxes + insurance + hoa + utilities + maintenance
            )

            cashflows.append(
                MonthlyCashflow(
                    month=month,
                    gross_revenue=round(gross, 2),
                    management_fee=round(mgmt_fee, 2),
                    cleaning_costs=round(cleaning, 2),
                    platform_fees=round(platform_fee, 2),
                    mortgage=round(mortgage, 2),
                    taxes=round(taxes, 2),
                    insurance=round(insurance, 2),
                    hoa=round(hoa, 2),
                    utilities=round(utilities, 2),
                    maintenance=round(maintenance, 2),
                    net_cashflow=round(gross - total_exp, 2),
                )
            )

        return cashflows

    @staticmethod
    def _monthly_mortgage(principal: float, annual_rate: float, years: int) -> float:
        """Calculate monthly mortgage payment (P&I) using standard amortization."""
        if annual_rate == 0 or principal == 0:
            return 0.0
        monthly_rate = annual_rate / 12
        n_payments = years * 12
        payment = principal * (
            monthly_rate * (1 + monthly_rate) ** n_payments
        ) / ((1 + monthly_rate) ** n_payments - 1)
        return round(payment, 2)

    @staticmethod
    def _break_even_occupancy(
        total_annual_costs: float, annual_revenue_at_full: float
    ) -> float:
        """Calculate occupancy rate needed to break even."""
        if annual_revenue_at_full <= 0:
            return 1.0
        # Revenue at full occupancy (scale up from current estimate)
        break_even = total_annual_costs / annual_revenue_at_full
        return min(break_even, 1.0)

    # ── Sensitivity Analysis ──

    def _build_sensitivity_analysis(
        self,
        prop: PropertyListing,
        scenario: FinancingScenario,
        annual_revenue: float,
        market: MarketMetrics,
        base_metrics: InvestmentMetrics,
    ) -> SensitivityAnalysis:
        """Build revenue × expense sensitivity matrix with seasonal normalization.

        Revenue stress levels test ±10–20% swings. An additional "Off-Peak"
        level strips holiday/seasonal premiums by capping each month's
        seasonality factor at the median, showing floor performance if the
        property cannot command peak-season rates.

        Expense factor is applied only to operating costs — the mortgage
        (a fixed contractual obligation) is unchanged.
        """
        # Revenue stress levels
        revenue_levels: list[tuple[str, float]] = [
            ("-20%", 0.80),
            ("-10%", 0.90),
            ("Base", 1.00),
            ("+10%", 1.10),
            ("+20%", 1.20),
        ]

        # Compute seasonal normalization factor and add Off-Peak level
        seasonal_norm = self._seasonal_normalization_factor(market)
        if seasonal_norm < 0.97:
            # Insert before the -20% level so it appears at the conservative end
            revenue_levels.insert(
                0, (f"Off-Peak ({seasonal_norm:.0%})", seasonal_norm)
            )

        # Expense stress levels (operating costs only, not mortgage)
        expense_levels: list[tuple[str, float]] = [
            ("Base", 1.00),
            ("+10%", 1.10),
            ("+20%", 1.20),
        ]

        # Extract expense components from base monthly cashflows
        base_cashflows = base_metrics.monthly_cashflows
        base_annual_revenue = base_metrics.annual_gross_revenue
        annual_debt_service = scenario.monthly_payment * 12

        # Revenue-proportional costs (management, platform, maintenance)
        total_variable = sum(
            cf.management_fee + cf.platform_fees + cf.maintenance
            for cf in base_cashflows
        )
        # Occupancy-driven (semi-variable — more bookings = more turns)
        total_cleaning = sum(cf.cleaning_costs for cf in base_cashflows)
        # Fixed operating costs (taxes, insurance, HOA, utilities)
        total_fixed_ops = sum(
            cf.taxes + cf.insurance + cf.hoa + cf.utilities
            for cf in base_cashflows
        )

        cases = []
        for rev_label, rev_factor in revenue_levels:
            for exp_label, exp_factor in expense_levels:
                # Adjusted revenue
                adj_revenue = base_annual_revenue * rev_factor

                # Variable costs scale with revenue AND expense factor
                adj_variable = total_variable * rev_factor * exp_factor
                adj_cleaning = total_cleaning * rev_factor * exp_factor
                # Fixed ops scale only with expense factor
                adj_fixed = total_fixed_ops * exp_factor

                total_operating = adj_variable + adj_cleaning + adj_fixed
                noi = adj_revenue - total_operating
                net_cashflow = noi - annual_debt_service

                cap_rate = noi / prop.list_price if prop.list_price > 0 else 0
                coc = (
                    net_cashflow / scenario.total_cash_needed
                    if scenario.total_cash_needed > 0
                    else 0
                )
                dscr = (
                    noi / annual_debt_service
                    if annual_debt_service > 0
                    else None
                )

                cases.append(
                    SensitivityCase(
                        label=f"Rev {rev_label} / Exp {exp_label}",
                        revenue_factor=rev_factor,
                        expense_factor=exp_factor,
                        annual_revenue=round(adj_revenue, 2),
                        annual_expenses=round(
                            total_operating + annual_debt_service, 2
                        ),
                        noi=round(noi, 2),
                        annual_net_cashflow=round(net_cashflow, 2),
                        cash_on_cash_return=round(coc, 4),
                        cap_rate=round(cap_rate, 4),
                        dscr=round(dscr, 2) if dscr is not None else None,
                    )
                )

        # Seasonal concentration metrics
        peak_pct = self._peak_months_revenue_share(base_cashflows)
        off_peak_annual = base_annual_revenue * seasonal_norm

        seasonal_note = ""
        if peak_pct > 0.35:
            seasonal_note = (
                f"Top 3 months account for {peak_pct:.0%} of annual revenue. "
                f"Off-peak normalized annual revenue is ${off_peak_annual:,.0f}. "
                "Consider the Off-Peak scenario for conservative underwriting."
            )
        elif peak_pct > 0.28:
            seasonal_note = (
                f"Top 3 months account for {peak_pct:.0%} of annual revenue "
                "— moderate seasonal concentration."
            )

        return SensitivityAnalysis(
            scenario_name=scenario.name,
            cases=cases,
            revenue_levels=[label for label, _ in revenue_levels],
            expense_levels=[label for label, _ in expense_levels],
            peak_months_revenue_pct=round(peak_pct, 4),
            off_peak_normalized_annual=round(off_peak_annual, 2),
            seasonal_risk_note=seasonal_note,
        )

    @staticmethod
    def _seasonal_normalization_factor(market: MarketMetrics) -> float:
        """Compute factor that strips peak/holiday premiums from revenue.

        Caps each month's seasonality factor at the median, showing what
        performance looks like without holiday/peak pricing power.  A factor
        of 0.85 means the property would earn ~85% of its projected annual
        revenue if it could never exceed off-peak nightly rates.
        """
        if not market.seasonality_index or len(market.seasonality_index) < 12:
            return 1.0

        factors = list(market.seasonality_index.values())
        sorted_factors = sorted(factors)
        median = sorted_factors[len(sorted_factors) // 2]

        # Cap each month at median (strips peak premiums)
        capped = [min(f, median) for f in factors]
        capped_total = sum(capped)
        original_total = sum(factors)

        if original_total <= 0:
            return 1.0

        return round(capped_total / original_total, 3)

    @staticmethod
    def _peak_months_revenue_share(
        cashflows: list[MonthlyCashflow],
    ) -> float:
        """Calculate what fraction of annual revenue comes from the top 3 months."""
        if not cashflows:
            return 0.25  # Default: evenly distributed

        monthly_revenues = sorted(
            [cf.gross_revenue for cf in cashflows], reverse=True
        )
        total = sum(monthly_revenues)
        if total <= 0:
            return 0.25

        top_3 = sum(monthly_revenues[:3])
        return top_3 / total

    def _calculate_suggested_offer(
        self,
        prop: PropertyListing,
        revenue: DualRevenueEstimate,
        market: MarketMetrics,
        purchase_comps: Optional[list[PurchaseComp]] = None,
    ) -> SuggestedOffer:
        """Calculate a data-driven suggested offer price.

        Factors considered:
        1. Days on market (DOM) — stale listings warrant larger discounts
        2. Purchase comp valuation — what similar properties sold for
        3. Income approach — price implied by target cap rate / CoC
        4. Market conditions — occupancy, revenue growth
        """
        list_price = prop.list_price
        factors: dict[str, str] = {}
        adjustments: list[float] = []  # Each is a multiplier (e.g., 0.95 = 5% below)

        # ── Factor 1: Days on Market ──
        dom = prop.days_on_market or 0
        if dom > 180:
            dom_adj = 0.88  # 12% below — very stale
            factors["Days on Market"] = f"{dom} days — significantly stale, aggressive discount"
        elif dom > 120:
            dom_adj = 0.92  # 8% below
            factors["Days on Market"] = f"{dom} days — stale listing, notable discount"
        elif dom > 60:
            dom_adj = 0.95  # 5% below
            factors["Days on Market"] = f"{dom} days — moderate time, some leverage"
        elif dom > 30:
            dom_adj = 0.97  # 3% below
            factors["Days on Market"] = f"{dom} days — reasonable time on market"
        else:
            dom_adj = 1.0  # No DOM discount
            factors["Days on Market"] = f"{dom} days — fresh listing, limited discount"
        adjustments.append(dom_adj)

        # ── Factor 2: Purchase Comps ──
        comp_value = None
        if purchase_comps:
            adjusted_prices = [
                c.adjusted_price for c in purchase_comps
                if c.adjusted_price and c.adjusted_price > 0
            ]
            if adjusted_prices:
                median_comp = sorted(adjusted_prices)[len(adjusted_prices) // 2]
                comp_value = median_comp
                ratio = list_price / median_comp if median_comp > 0 else 1
                if ratio > 1.10:
                    comp_adj = median_comp / list_price
                    factors["Comp Valuation"] = (
                        f"Listed {ratio:.0%} above comp median "
                        f"(${median_comp:,.0f}) — overpriced"
                    )
                elif ratio > 1.0:
                    comp_adj = 0.98
                    factors["Comp Valuation"] = (
                        f"Listed slightly above comp median "
                        f"(${median_comp:,.0f})"
                    )
                elif ratio > 0.90:
                    comp_adj = 1.0
                    factors["Comp Valuation"] = (
                        f"Priced near or below comps "
                        f"(${median_comp:,.0f}) — fairly priced"
                    )
                else:
                    comp_adj = 1.0
                    factors["Comp Valuation"] = (
                        f"Priced well below comps "
                        f"(${median_comp:,.0f}) — potential deal"
                    )
                adjustments.append(comp_adj)

        # ── Factor 3: Income Approach (target 10% CoC) ──
        target_coc = 0.10
        moderate_noi = revenue.moderate_revenue * 0.45  # rough NOI margin
        if moderate_noi > 0:
            # Price that would yield target CoC under conventional financing
            down_pct = self.financing.conventional_down_pct
            closing_pct = self.financing.closing_cost_pct
            furnishing = self.costs.furnishing_per_bed * prop.beds
            # Back-solve: CoC = (NOI - debt_svc) / (down + closing + furnish)
            # Simplified: income-implied price ≈ NOI / target_cap_rate
            target_cap = 0.08
            income_price = int(moderate_noi / target_cap) if target_cap > 0 else list_price
            income_ratio = income_price / list_price if list_price > 0 else 1
            income_adj = min(max(income_ratio, 0.75), 1.10)  # cap adjustments
            factors["Income Approach"] = (
                f"At 8% target cap rate, income supports "
                f"${income_price:,.0f} "
                f"({'above' if income_price > list_price else 'below'} list)"
            )
            adjustments.append(income_adj)

        # ── Factor 4: Market Conditions ──
        if market.occupancy_rate < 0.50:
            mkt_adj = 0.93
            factors["Market Conditions"] = (
                f"Low market occupancy ({market.occupancy_rate:.0%}) — "
                "soft demand, larger discount justified"
            )
        elif market.occupancy_rate < 0.60:
            mkt_adj = 0.96
            factors["Market Conditions"] = (
                f"Below-average occupancy ({market.occupancy_rate:.0%})"
            )
        elif market.occupancy_rate > 0.75:
            mkt_adj = 1.0
            factors["Market Conditions"] = (
                f"Strong occupancy ({market.occupancy_rate:.0%}) — "
                "healthy demand"
            )
        else:
            mkt_adj = 0.98
            factors["Market Conditions"] = (
                f"Average occupancy ({market.occupancy_rate:.0%})"
            )
        adjustments.append(mkt_adj)

        # ── Combine factors ──
        combined_multiplier = 1.0
        for adj in adjustments:
            combined_multiplier *= adj

        # Clamp discount to reasonable range (max 20% below, max 5% above)
        combined_multiplier = max(0.80, min(1.05, combined_multiplier))

        offer_price = int(list_price * combined_multiplier)
        # Round to nearest $1,000
        offer_price = round(offer_price / 1000) * 1000
        discount_pct = 1.0 - (offer_price / list_price) if list_price > 0 else 0

        # Build rationale
        parts = []
        if discount_pct > 0.01:
            parts.append(
                f"Offer ${offer_price:,} ({discount_pct:.0%} below "
                f"list price of ${list_price:,})"
            )
        else:
            parts.append(f"Offer at or near list price ${offer_price:,}")

        if dom > 60:
            parts.append(f"Listing is stale at {dom} days on market")
        if comp_value and comp_value < list_price * 0.95:
            parts.append(f"Comp median (${comp_value:,.0f}) supports lower price")

        rationale = ". ".join(parts) + "."

        return SuggestedOffer(
            offer_price=offer_price,
            rationale=rationale,
            discount_pct=round(discount_pct, 4),
            factors=factors,
        )
