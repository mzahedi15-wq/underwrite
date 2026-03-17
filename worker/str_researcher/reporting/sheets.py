"""Google Sheets report builder.

All data writes use batch ``append_rows`` to minimise API calls and stay
within Google Sheets' 60 writes-per-minute quota.  A lightweight retry
wrapper handles transient 429 / 5xx errors with exponential back-off.
"""

from __future__ import annotations

import time
from typing import Optional

import gspread
from gspread.exceptions import APIError
from gspread_formatting import (
    CellFormat,
    Color,
    NumberFormat,
    TextFormat,
    format_cell_range,
    set_column_widths,
)

from str_researcher.models.report import AnalysisResult
from str_researcher.reporting.templates import (
    AMENITY_MATRIX_HEADERS,
    COLORS,
    FINANCING_ROWS,
    FINANCING_SCENARIO_HEADERS,
    MONTHLY_CASHFLOW_HEADERS,
    PURCHASE_COMP_HEADERS,
    RANKING_HEADERS,
    STR_COMP_HEADERS,
)
from str_researcher.utils.logging import get_logger

logger = get_logger("sheets")

# Pause between tabs to avoid burst rate-limiting (seconds)
_TAB_DELAY = 4


def _retry(fn, *args, max_retries: int = 3, **kwargs):
    """Call *fn* with exponential back-off on 429 / 5xx errors."""
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except APIError as exc:
            code = exc.response.status_code if hasattr(exc, "response") else 0
            if code in (429, 500, 502, 503) and attempt < max_retries:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                logger.warning(
                    "Sheets API %d — retrying in %ds (attempt %d/%d)",
                    code, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
            else:
                raise


class SheetsBuilder:
    """Builds Google Sheets reports from analysis results."""

    def __init__(self, gc: gspread.Client):
        self._gc = gc

    # ── Public API ──────────────────────────────────────────────────

    def create_master_ranking(
        self, results: list[AnalysisResult], title: str = "STR Investment Rankings"
    ) -> str:
        """Create a master ranking sheet with all properties.

        Returns the spreadsheet URL.
        """
        sh = _retry(self._gc.create, title)
        ws = sh.sheet1
        _retry(ws.update_title, "Rankings")

        # Build all data rows
        all_rows = [RANKING_HEADERS]
        for result in results:
            best_coc = max(
                (m.cash_on_cash_return for m in result.investment_metrics.values()),
                default=0,
            )
            best_cap = max(
                (m.cap_rate for m in result.investment_metrics.values()),
                default=0,
            )
            all_rows.append([
                result.investment_rank,
                result.property.full_address,
                result.property.list_price,
                result.property.beds,
                result.property.baths,
                result.revenue_estimate.moderate_revenue,
                result.revenue_estimate.aggressive_revenue,
                best_coc,
                best_cap,
                result.investment_score,
                result.property.source_url or "",
                result.sheet_url or "",
                result.scope_doc_url or "",
                result.marketing_doc_url or "",
            ])

        _retry(ws.append_rows, all_rows)

        # Formatting (read-only API calls — lighter quota)
        num_rows = len(all_rows)
        self._format_header_row(ws, len(RANKING_HEADERS))
        self._format_currency(ws, "C2", f"C{num_rows}")
        self._format_currency(ws, "F2", f"G{num_rows}")
        self._format_pct(ws, "H2", f"I{num_rows}")

        for i, result in enumerate(results, start=2):
            score = result.investment_score
            if score >= 70:
                color = COLORS["good"]
            elif score >= 50:
                color = COLORS["moderate"]
            else:
                color = COLORS["poor"]
            fmt = CellFormat(backgroundColor=Color(**color))
            format_cell_range(ws, f"A{i}:N{i}", fmt)

        set_column_widths(ws, [
            ("A", 50), ("B", 250), ("C", 120), ("D", 50), ("E", 50),
            ("F", 130), ("G", 130), ("H", 100), ("I", 100), ("J", 100),
            ("K", 200), ("L", 200), ("M", 200), ("N", 200),
        ])

        url = sh.url
        logger.info("Created master ranking sheet: %s", url)
        return url

    def create_property_sheet(
        self, result: AnalysisResult, title: Optional[str] = None
    ) -> str:
        """Create a detailed multi-tab sheet for a single property.

        Returns the spreadsheet URL.
        """
        if title is None:
            title = f"STR Analysis - {result.property.full_address[:40]}"

        sh = _retry(self._gc.create, title)

        # Build each tab with pauses to respect API rate limits
        builders = [
            self._build_executive_summary,
            self._build_monthly_cashflow,
            self._build_financing_scenarios,
            self._build_sensitivity_analysis,
            self._build_purchase_list,
            self._build_purchase_comps,
            self._build_str_comps,
            self._build_amenity_matrix,
            self._build_revenue_scenarios,
        ]

        for build_fn in builders:
            try:
                build_fn(sh, result)
            except Exception as e:
                logger.error("Tab %s failed: %s", build_fn.__name__, e)
            time.sleep(_TAB_DELAY)

        # Remove default Sheet1
        try:
            default = sh.worksheet("Sheet1")
            sh.del_worksheet(default)
        except gspread.exceptions.WorksheetNotFound:
            pass

        url = sh.url
        logger.info("Created property sheet: %s", url)
        return url

    # ── Private Tab Builders ────────────────────────────────────────

    def _build_executive_summary(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Executive Summary", rows=40, cols=5)
        prop = result.property
        rev = result.revenue_estimate

        # Find best financing scenario
        best_scenario_name = ""
        best_coc = -999.0
        best_metrics = None
        for name, metrics in result.investment_metrics.items():
            if metrics.cash_on_cash_return > best_coc:
                best_coc = metrics.cash_on_cash_return
                best_scenario_name = name
                best_metrics = metrics

        rows = [
            ["PROPERTY DETAILS", ""],
            ["Address", prop.full_address],
            ["Listing URL", prop.source_url or ""],
            ["List Price", f"${prop.list_price:,.0f}"],
            ["Beds / Baths", f"{prop.beds} / {prop.baths}"],
            ["Sqft", f"{prop.sqft:,.0f}" if prop.sqft else "Unknown"],
            ["Year Built", str(prop.year_built) if prop.year_built else "Unknown"],
            ["", ""],
            ["REVENUE ESTIMATES", ""],
            ["Conservative Revenue", f"${rev.conservative_revenue:,.0f}"],
            ["Moderate Revenue", f"${rev.moderate_revenue:,.0f}"],
            ["Aggressive Revenue", f"${rev.aggressive_revenue:,.0f}"],
            ["Moderate ADR", f"${rev.moderate_adr:,.0f}"],
            ["Moderate Occupancy", f"{rev.moderate_occupancy:.0%}"],
            ["", ""],
            ["BEST FINANCING SCENARIO", f"({best_scenario_name})"],
        ]

        if best_metrics:
            rows.extend([
                ["Down Payment", f"${best_metrics.financing.total_cash_needed:,.0f}"],
                ["Monthly Mortgage", f"${best_metrics.financing.monthly_payment:,.0f}"],
                ["Cash-on-Cash Return", f"{best_metrics.cash_on_cash_return:.1%}"],
                ["Cap Rate", f"{best_metrics.cap_rate:.1%}"],
                ["DSCR", f"{best_metrics.dscr:.2f}" if best_metrics.dscr is not None else "N/A"],
                ["Break-even Occupancy", f"{best_metrics.break_even_occupancy:.0%}"],
            ])

        # Suggested Offer (from first scenario that has one)
        offer = None
        for m in result.investment_metrics.values():
            if m.suggested_offer:
                offer = m.suggested_offer
                break

        if offer:
            rows.extend([
                ["", ""],
                ["SUGGESTED OFFER", ""],
                ["Offer Price", f"${offer.offer_price:,.0f}"],
                ["Discount from List", f"{offer.discount_pct:.0%}"],
                ["Rationale", offer.rationale],
            ])
            for factor, detail in offer.factors.items():
                rows.append([f"  {factor}", detail])

        rows.extend([
            ["", ""],
            ["INVESTMENT", ""],
            ["Investment Score", f"{result.investment_score:.0f} / 100"],
            ["Investment Rank", f"#{result.investment_rank}"],
        ])

        if result.investment_narrative:
            rows.extend([
                ["", ""],
                ["INVESTMENT THESIS", ""],
                [result.investment_narrative, ""],
            ])

        _retry(ws.append_rows, rows)

        # Format section headers bold
        section_headers = {
            "PROPERTY DETAILS", "REVENUE ESTIMATES",
            "BEST FINANCING SCENARIO", "SUGGESTED OFFER",
            "INVESTMENT", "INVESTMENT THESIS",
        }
        bold = CellFormat(textFormat=TextFormat(bold=True))
        section_bg = CellFormat(backgroundColor=Color(**COLORS["section_divider"]))
        for i, row in enumerate(rows, start=1):
            if row[0] in section_headers:
                format_cell_range(ws, f"A{i}:B{i}", bold)
                format_cell_range(ws, f"A{i}:B{i}", section_bg)

        set_column_widths(ws, [("A", 220), ("B", 350)])

    def _build_monthly_cashflow(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Monthly Cashflow", rows=20, cols=16)

        # Use moderate scenario or first available
        metrics = None
        for name in ["Conventional - Moderate", "Conventional", "DSCR - Moderate"]:
            if name in result.investment_metrics:
                metrics = result.investment_metrics[name]
                break
        if metrics is None and result.investment_metrics:
            metrics = next(iter(result.investment_metrics.values()))

        all_rows = [MONTHLY_CASHFLOW_HEADERS]

        if metrics and metrics.monthly_cashflows:
            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
            for i, cf in enumerate(metrics.monthly_cashflows):
                all_rows.append([
                    month_names[i] if i < 12 else f"Month {i+1}",
                    cf.gross_revenue,
                    "",  # occupancy (per-month not tracked)
                    cf.management_fee,
                    cf.cleaning_costs,
                    cf.platform_fees,
                    cf.taxes,
                    cf.insurance,
                    cf.hoa,
                    cf.utilities,
                    cf.maintenance,
                    cf.mortgage,
                    0,  # vacancy reserve
                    cf.total_expenses,
                    cf.net_cashflow,
                ])

            # Totals row
            total_rev = sum(cf.gross_revenue for cf in metrics.monthly_cashflows)
            total_exp = sum(cf.total_expenses for cf in metrics.monthly_cashflows)
            total_net = sum(cf.net_cashflow for cf in metrics.monthly_cashflows)
            all_rows.append([
                "TOTAL", total_rev, "", "", "", "", "",
                "", "", "", "", "", "", total_exp, total_net,
            ])

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(MONTHLY_CASHFLOW_HEADERS))

    def _build_financing_scenarios(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Financing Scenarios", rows=25, cols=5)

        # Gather metrics by type
        scenarios = {}
        for name, m in result.investment_metrics.items():
            key = name.split(" - ")[0] if " - " in name else name
            if key not in scenarios:
                scenarios[key] = m

        conv = scenarios.get("Conventional")
        dscr = scenarios.get("DSCR")
        cash = scenarios.get("Cash")

        all_rows = [FINANCING_SCENARIO_HEADERS]

        for row_label in FINANCING_ROWS:
            if row_label == "":
                all_rows.append([""])
                continue
            if row_label.startswith("---"):
                all_rows.append([row_label.strip("- "), "", "", ""])
                continue

            row = [row_label]
            for m in [conv, dscr, cash]:
                if m is None:
                    row.append("N/A")
                    continue
                f = m.financing
                if row_label == "Down Payment %":
                    pct = f.down_payment / f.purchase_price if f.purchase_price else 0
                    row.append(f"{pct:.0%}")
                elif row_label == "Down Payment $":
                    row.append(f"${f.down_payment:,.0f}")
                elif row_label == "Interest Rate":
                    row.append(f"{f.interest_rate:.1%}")
                elif row_label == "Loan Amount":
                    row.append(f"${f.loan_amount:,.0f}")
                elif row_label == "Monthly Payment":
                    row.append(f"${f.monthly_payment:,.0f}")
                elif row_label == "Closing Costs":
                    row.append(f"${f.closing_costs:,.0f}")
                elif row_label == "Renovation & Furnishing":
                    row.append(f"${f.renovation_furnishing:,.0f}")
                elif row_label == "Total Cash Needed":
                    row.append(f"${f.total_cash_needed:,.0f}")
                elif row_label == "Gross Revenue":
                    row.append(f"${m.annual_gross_revenue:,.0f}")
                elif row_label == "Total Expenses":
                    row.append(f"${m.annual_expenses:,.0f}")
                elif row_label == "NOI":
                    row.append(f"${m.noi:,.0f}")
                elif row_label == "Annual Debt Service":
                    row.append(f"${f.monthly_payment * 12:,.0f}")
                elif row_label == "Cash Flow":
                    row.append(f"${m.annual_net_cashflow:,.0f}")
                elif row_label == "Cap Rate":
                    row.append(f"{m.cap_rate:.1%}")
                elif row_label == "Cash-on-Cash Return":
                    row.append(f"{m.cash_on_cash_return:.1%}")
                elif row_label == "DSCR":
                    row.append(f"{m.dscr:.2f}x" if m.dscr is not None else "N/A")
                elif row_label == "Break-even Occupancy":
                    row.append(f"{m.break_even_occupancy:.0%}")
                elif row_label == "Suggested Offer Price":
                    if m.suggested_offer:
                        row.append(f"${m.suggested_offer.offer_price:,.0f}")
                    else:
                        row.append("N/A")
                elif row_label == "Offer Rationale":
                    if m.suggested_offer:
                        row.append(m.suggested_offer.rationale)
                    else:
                        row.append("")
                else:
                    row.append("")
            all_rows.append(row)

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(FINANCING_SCENARIO_HEADERS))
        set_column_widths(ws, [("A", 200), ("B", 150), ("C", 150), ("D", 150)])

    def _build_sensitivity_analysis(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        """Build sensitivity analysis tab with revenue × expense matrices."""
        sens = None
        sens_scenario = ""
        for name in ["Conventional", "DSCR", "Cash"]:
            if name in result.investment_metrics:
                metrics = result.investment_metrics[name]
                if metrics.sensitivity:
                    sens = metrics.sensitivity
                    sens_scenario = name
                    break

        if sens is None or not sens.cases:
            return

        n_rev = len(sens.revenue_levels)
        n_exp = len(sens.expense_levels)
        ws = _retry(
            sh.add_worksheet,
            "Sensitivity Analysis",
            rows=max(60, n_rev * 4 + 30),
            cols=max(8, n_exp + 3),
        )

        all_rows: list[list[str]] = []
        all_rows.append([f"Sensitivity Analysis — {sens_scenario} Financing"])

        if sens.seasonal_risk_note:
            all_rows.append([sens.seasonal_risk_note])

        all_rows.append(["Peak 3-Month Revenue Share", f"{sens.peak_months_revenue_pct:.0%}"])
        all_rows.append(["Off-Peak Normalized Revenue", f"${sens.off_peak_normalized_annual:,.0f}"])
        all_rows.append([""])

        def _fv(v, fmt: str) -> str:
            if v is None:
                return "N/A"
            if fmt == "%":
                return f"{v:.1%}"
            elif fmt == "$":
                return f"${v:,.0f}"
            elif fmt == "x":
                return f"{v:.2f}x"
            return str(v)

        def _lookup(rev_label: str, exp_label: str, attr: str):
            target = f"Rev {rev_label} / Exp {exp_label}"
            for case in sens.cases:
                if case.label == target:
                    return getattr(case, attr)
            return None

        def _matrix(title: str, attr: str, fmt: str) -> None:
            all_rows.append([title])
            all_rows.append(
                ["Revenue \\ Expenses"] + [f"Exp {lbl}" for lbl in sens.expense_levels]
            )
            for rev_label in sens.revenue_levels:
                row = [f"Rev {rev_label}"]
                for exp_label in sens.expense_levels:
                    row.append(_fv(_lookup(rev_label, exp_label, attr), fmt))
                all_rows.append(row)
            all_rows.append([""])

        _matrix("Cash-on-Cash Return", "cash_on_cash_return", "%")
        _matrix("Annual Net Cashflow", "annual_net_cashflow", "$")
        if sens_scenario != "Cash":
            _matrix("DSCR (Debt Service Coverage)", "dscr", "x")

        _retry(ws.append_rows, all_rows)

        # Formatting
        bold_title = CellFormat(textFormat=TextFormat(bold=True, fontSize=12))
        format_cell_range(ws, "A1:A1", bold_title)

        col_end = chr(ord("A") + n_exp)
        row_idx = 1
        for row_data in all_rows:
            label = row_data[0] if row_data else ""
            if label in ("Cash-on-Cash Return", "Annual Net Cashflow",
                         "DSCR (Debt Service Coverage)"):
                fmt = CellFormat(
                    textFormat=TextFormat(bold=True),
                    backgroundColor=Color(**COLORS["section_divider"]),
                )
                format_cell_range(ws, f"A{row_idx}:{col_end}{row_idx}", fmt)
            elif label == "Revenue \\ Expenses":
                hdr_fmt = CellFormat(
                    textFormat=TextFormat(
                        bold=True,
                        foregroundColor=Color(**COLORS["header_text"]),
                    ),
                    backgroundColor=Color(**COLORS["header_bg"]),
                )
                format_cell_range(ws, f"A{row_idx}:{col_end}{row_idx}", hdr_fmt)
            row_idx += 1

        widths = [("A", 200)] + [
            (chr(ord("B") + i), 140) for i in range(n_exp)
        ]
        set_column_widths(ws, widths)

    def _build_purchase_list(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        """Build the furnishing / renovation purchase list tab."""
        scope = result.scope_of_work
        if not scope or not scope.recommendations:
            return

        # Collect all purchase items across all recommendations
        all_items = []
        for rec in scope.recommendations:
            for item in rec.purchase_items:
                all_items.append((rec.category, rec.priority, item))

        if not all_items:
            return

        ws = _retry(
            sh.add_worksheet, "Purchase List",
            rows=max(30, len(all_items) + 10), cols=9,
        )

        headers = [
            "Category", "Priority", "Item", "Qty",
            "Unit Cost", "Line Total", "Store", "Notes", "Link",
        ]
        all_rows = [headers]
        grand_total = 0.0

        for cat, priority, item in all_items:
            line_total = item.estimated_cost * item.quantity
            grand_total += line_total
            all_rows.append([
                cat,
                priority.replace("_", " ").title(),
                item.item_name,
                item.quantity,
                item.estimated_cost,
                line_total,
                item.store,
                item.notes,
                item.product_url,
            ])

        # Totals row
        all_rows.append(["", "", "", "", "", "", "", "", ""])
        all_rows.append(["", "", "TOTAL", "", "", grand_total, "", "", ""])

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(headers))

        num_rows = len(all_rows)
        self._format_currency(ws, "E2", f"F{num_rows}")
        set_column_widths(ws, [
            ("A", 100), ("B", 100), ("C", 300), ("D", 50),
            ("E", 100), ("F", 100), ("G", 100), ("H", 200), ("I", 350),
        ])

    def _build_purchase_comps(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Purchase Comps", rows=20, cols=10)

        all_rows = [PURCHASE_COMP_HEADERS]
        for comp in result.purchase_comps:
            adj_str = (
                ", ".join(f"{k}: ${v:+,.0f}" for k, v in comp.adjustments.items())
                if comp.adjustments else ""
            )
            all_rows.append([
                comp.address,
                comp.sale_price,
                comp.beds,
                comp.baths,
                comp.sqft or "",
                comp.sale_date or "",
                f"{comp.distance_miles:.1f}" if comp.distance_miles else "",
                adj_str,
                comp.adjusted_price or "",
            ])

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(PURCHASE_COMP_HEADERS))

    def _build_str_comps(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "STR Comps", rows=50, cols=11)

        all_rows = [STR_COMP_HEADERS]
        top_rows: list[int] = []  # 1-indexed row numbers of top performers

        for comp in result.str_comps:
            all_rows.append([
                comp.title[:50],
                comp.platform,
                comp.beds,
                comp.nightly_rate_avg,
                comp.annual_revenue_est,
                comp.review_score,
                comp.review_count,
                "Yes" if comp.superhost else "No",
                "Yes" if comp.is_top_performer else "No",
                ", ".join(comp.amenities[:8]),
            ])
            if comp.is_top_performer:
                top_rows.append(len(all_rows))  # current row number (1-indexed)

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(STR_COMP_HEADERS))

        # Highlight top performers (small number of format calls)
        top_fmt = CellFormat(backgroundColor=Color(**COLORS["top_performer"]))
        for row_num in top_rows:
            format_cell_range(ws, f"A{row_num}:J{row_num}", top_fmt)

    def _build_amenity_matrix(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Amenity Matrix", rows=30, cols=6)

        all_rows = [AMENITY_MATRIX_HEADERS]
        if result.scope_of_work and result.scope_of_work.amenity_gap_analysis:
            for am in result.scope_of_work.amenity_gap_analysis:
                gap = am.prevalence_top_pct - am.prevalence_all_pct
                all_rows.append([
                    am.amenity_name,
                    f"{am.prevalence_top_pct:.0%}",
                    f"{am.prevalence_all_pct:.0%}",
                    f"{gap:+.0%}",
                    "YES" if am.is_differentiator else "",
                ])

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(AMENITY_MATRIX_HEADERS))

    def _build_revenue_scenarios(
        self, sh: gspread.Spreadsheet, result: AnalysisResult
    ) -> None:
        ws = _retry(sh.add_worksheet, "Revenue Scenarios", rows=15, cols=8)
        rev = result.revenue_estimate

        headers = ["Source / Scenario", "Annual Revenue", "ADR", "Occupancy"]
        all_rows = [headers]

        all_rows.extend([
            [
                "AirDNA Estimate",
                f"${rev.airdna_estimate.annual_revenue:,.0f}" if rev.airdna_estimate else "N/A",
                f"${rev.airdna_estimate.adr:,.0f}" if rev.airdna_estimate else "",
                f"{rev.airdna_estimate.occupancy_rate:.0%}" if rev.airdna_estimate else "",
            ],
            [
                "Airbnb Comp Estimate",
                f"${rev.comp_estimate.annual_revenue:,.0f}" if rev.comp_estimate else "N/A",
                f"${rev.comp_estimate.adr:,.0f}" if rev.comp_estimate else "",
                f"{rev.comp_estimate.occupancy_rate:.0%}" if rev.comp_estimate else "",
            ],
            ["", "", "", ""],
            [
                "Conservative",
                f"${rev.conservative_revenue:,.0f}",
                f"${rev.conservative_adr:,.0f}",
                f"{rev.conservative_occupancy:.0%}",
            ],
            [
                "Moderate (Blended)",
                f"${rev.moderate_revenue:,.0f}",
                f"${rev.moderate_adr:,.0f}",
                f"{rev.moderate_occupancy:.0%}",
            ],
            [
                "Aggressive (Top 10%)",
                f"${rev.aggressive_revenue:,.0f}",
                f"${rev.aggressive_adr:,.0f}",
                f"{rev.aggressive_occupancy:.0%}",
            ],
        ])

        if rev.needs_manual_review:
            all_rows.append(["", "", "", ""])
            all_rows.append([
                "⚠ DIVERGENCE WARNING",
                f"{rev.divergence_pct:.0%} gap between estimates",
                "", "",
            ])

        _retry(ws.append_rows, all_rows)
        self._format_header_row(ws, len(headers))
        set_column_widths(ws, [("A", 200), ("B", 150), ("C", 100), ("D", 100)])

    # ── Formatting Helpers ──────────────────────────────────────────

    @staticmethod
    def _format_header_row(ws: gspread.Worksheet, num_cols: int) -> None:
        col_letter = chr(ord("A") + num_cols - 1)
        fmt = CellFormat(
            textFormat=TextFormat(
                bold=True,
                foregroundColor=Color(**COLORS["header_text"]),
            ),
            backgroundColor=Color(**COLORS["header_bg"]),
        )
        format_cell_range(ws, f"A1:{col_letter}1", fmt)

    @staticmethod
    def _format_currency(ws: gspread.Worksheet, start: str, end: str) -> None:
        fmt = CellFormat(numberFormat=NumberFormat(type="CURRENCY", pattern="$#,##0"))
        format_cell_range(ws, f"{start}:{end}", fmt)

    @staticmethod
    def _format_pct(ws: gspread.Worksheet, start: str, end: str) -> None:
        fmt = CellFormat(numberFormat=NumberFormat(type="PERCENT", pattern="0.0%"))
        format_cell_range(ws, f"{start}:{end}", fmt)
