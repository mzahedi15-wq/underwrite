"""Property Detail page - Deep dive on a single property."""

import streamlit as st
import pandas as pd


def _rdylgn_color(val: float, vmin: float, vmax: float) -> str:
    """Map a numeric value to a Red-Yellow-Green background CSS string.

    Pure Python — no matplotlib needed.  Linearly interpolates between
    Red (#d73027) ↔ Yellow (#fee08b) ↔ Green (#1a9850).
    """
    if pd.isna(val):
        return ""
    # Clamp to [0, 1]
    t = max(0.0, min(1.0, (val - vmin) / (vmax - vmin))) if vmax != vmin else 0.5

    if t < 0.5:
        # Red → Yellow (t from 0 → 0.5)
        s = t * 2  # remap to 0..1
        r = int(215 + s * (254 - 215))
        g = int(48 + s * (224 - 48))
        b = int(39 + s * (139 - 39))
    else:
        # Yellow → Green (t from 0.5 → 1)
        s = (t - 0.5) * 2  # remap to 0..1
        r = int(254 + s * (26 - 254))
        g = int(224 + s * (152 - 224))
        b = int(139 + s * (80 - 139))

    return f"background-color: rgb({r},{g},{b}); color: #222"


def _style_heatmap(df: pd.DataFrame, fmt: str, vmin: float, vmax: float):
    """Apply RdYlGn heatmap coloring + number format to a DataFrame."""
    return df.style.format(fmt).map(
        lambda v: _rdylgn_color(v, vmin, vmax)
    )


st.title("Property Detail")

results = st.session_state.get("results")
idx = st.session_state.get("selected_property_index")

if results is None or idx is None:
    st.info("No property selected. Go to **Rankings** to select a property.")
    st.stop()

result = results[idx]
prop = result.property

# Property header
col1, col2 = st.columns([2, 1])
with col1:
    st.header(prop.full_address)
    st.caption(f"Source: {prop.source.title()} | Listed: {prop.days_on_market or 'N/A'} days ago")
with col2:
    st.metric("List Price", f"${prop.list_price:,}")
    st.metric("Investment Score", f"{result.investment_score:.1f}")
    st.metric("Rank", f"#{result.investment_rank}")

st.divider()

# Property details
st.subheader("Property Details")
detail_cols = st.columns(5)
with detail_cols[0]:
    st.metric("Beds", prop.beds)
with detail_cols[1]:
    st.metric("Baths", prop.baths)
with detail_cols[2]:
    st.metric("Sqft", f"{prop.sqft:,}" if prop.sqft else "N/A")
with detail_cols[3]:
    st.metric("Year Built", prop.year_built or "N/A")
with detail_cols[4]:
    st.metric("$/Sqft", f"${prop.price_per_sqft:,.0f}" if prop.price_per_sqft else "N/A")

st.divider()

# Market Data Source indicator
market = result.market_metrics
if market.market_id == "comp_derived":
    st.info(
        f"📊 **Market data derived from {market.active_listing_count} Airbnb/VRBO comps** — "
        f"ADR ${market.adr:.0f}, Occupancy {market.occupancy_rate:.0%}, RevPAR ${market.revpar:.0f}"
    )
elif market.market_id == "default_fallback":
    st.warning(
        "⚠️ **Market data using conservative defaults** — no AirDNA key and no STR comps available. "
        "Revenue estimates may be less accurate."
    )
elif market.market_id not in ("unknown", "pending_comps"):
    st.success(
        f"✅ **Market data from AirDNA** — "
        f"ADR ${market.adr:.0f}, Occupancy {market.occupancy_rate:.0%}, RevPAR ${market.revpar:.0f}"
    )

# Dual Revenue Comparison
st.subheader("Revenue Estimation")
rev = result.revenue_estimate

rev_col1, rev_col2, rev_col3 = st.columns(3)
with rev_col1:
    st.markdown("**AirDNA Rentalizer**")
    if rev.airdna_estimate:
        st.metric("Annual Revenue", f"${rev.airdna_estimate.annual_revenue:,.0f}")
        st.metric("ADR", f"${rev.airdna_estimate.adr:,.0f}")
        st.metric("Occupancy", f"{rev.airdna_estimate.occupancy_rate:.0%}")
    else:
        st.warning("AirDNA estimate unavailable")

with rev_col2:
    st.markdown("**Airbnb Comp Analysis**")
    if rev.comp_estimate:
        st.metric("Annual Revenue", f"${rev.comp_estimate.annual_revenue:,.0f}")
        st.metric("ADR", f"${rev.comp_estimate.adr:,.0f}")
        st.metric("Occupancy", f"{rev.comp_estimate.occupancy_rate:.0%}")
    else:
        st.warning("Comp estimate unavailable")

with rev_col3:
    st.markdown("**Reconciled Scenarios**")
    st.metric("Conservative", f"${rev.conservative_revenue:,.0f}")
    st.metric("Moderate (Blended)", f"${rev.moderate_revenue:,.0f}")
    st.metric("Aggressive", f"${rev.aggressive_revenue:,.0f}")
    if rev.needs_manual_review:
        st.warning(f"Estimates diverge by {rev.divergence_pct:.0%} — review recommended")

st.divider()

# Financial Summary
st.subheader("Financial Analysis")
if result.investment_metrics:
    fin_tabs = st.tabs(list(result.investment_metrics.keys()))
    for tab, (scenario_name, metrics) in zip(fin_tabs, result.investment_metrics.items()):
        with tab:
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("NOI", f"${metrics.noi:,.0f}")
                st.metric("Cap Rate", f"{metrics.cap_rate:.1%}")
            with m_col2:
                st.metric("Cash-on-Cash", f"{metrics.cash_on_cash_return:.1%}")
                st.metric("DSCR", f"{metrics.dscr:.2f}" if metrics.dscr is not None else "N/A")
            with m_col3:
                st.metric("Break-Even Occ.", f"{metrics.break_even_occupancy:.0%}")
                st.metric("Annual Net Cashflow", f"${metrics.annual_net_cashflow:,.0f}")
            with m_col4:
                st.metric("Total Cash Needed", f"${metrics.financing.total_cash_needed:,.0f}")
                st.metric("Monthly Mortgage", f"${metrics.financing.monthly_payment:,.0f}")

            # Monthly cashflow chart
            if metrics.monthly_cashflows:
                cf_data = pd.DataFrame(
                    [
                        {
                            "Month": m.month,
                            "Revenue": m.gross_revenue,
                            "Expenses": m.total_expenses,
                            "Net Cashflow": m.net_cashflow,
                        }
                        for m in metrics.monthly_cashflows
                    ]
                )
                st.bar_chart(cf_data.set_index("Month")[["Revenue", "Net Cashflow"]])

st.divider()

# Sensitivity Analysis
st.subheader("Sensitivity Analysis")
st.caption(
    "Stress-tests key returns under different revenue and expense assumptions. "
    "The Off-Peak scenario strips holiday/seasonal premiums to show floor performance."
)
if result.investment_metrics:
    sens_tabs = st.tabs(list(result.investment_metrics.keys()))
    for s_tab, (s_name, s_metrics) in zip(
        sens_tabs, result.investment_metrics.items()
    ):
        with s_tab:
            sens = s_metrics.sensitivity
            if not sens or not sens.cases:
                st.info("Sensitivity data not available for this scenario.")
                continue

            # Seasonal risk warning
            if sens.seasonal_risk_note:
                st.warning(sens.seasonal_risk_note)

            # ── Cash-on-Cash Return matrix ──
            st.markdown("**Cash-on-Cash Return**")
            coc_rows = []
            for rev_label in sens.revenue_levels:
                row = {}
                for exp_label in sens.expense_levels:
                    target = f"Rev {rev_label} / Exp {exp_label}"
                    for case in sens.cases:
                        if case.label == target:
                            row[f"Exp {exp_label}"] = case.cash_on_cash_return
                            break
                coc_rows.append(row)

            coc_df = pd.DataFrame(
                coc_rows,
                index=[f"Rev {lbl}" for lbl in sens.revenue_levels],
            )
            styled_coc = _style_heatmap(coc_df, "{:.1%}", -0.10, 0.15)
            st.dataframe(styled_coc, use_container_width=True)

            # ── Annual Net Cashflow matrix ──
            st.markdown("**Annual Net Cashflow**")
            cf_rows = []
            for rev_label in sens.revenue_levels:
                row = {}
                for exp_label in sens.expense_levels:
                    target = f"Rev {rev_label} / Exp {exp_label}"
                    for case in sens.cases:
                        if case.label == target:
                            row[f"Exp {exp_label}"] = case.annual_net_cashflow
                            break
                cf_rows.append(row)

            cf_df = pd.DataFrame(
                cf_rows,
                index=[f"Rev {lbl}" for lbl in sens.revenue_levels],
            )
            styled_cf = _style_heatmap(cf_df, "${:,.0f}", -20000, 30000)
            st.dataframe(styled_cf, use_container_width=True)

            # ── DSCR matrix ──
            if s_name != "Cash":
                st.markdown("**DSCR (Debt Service Coverage)**")
                dscr_rows = []
                for rev_label in sens.revenue_levels:
                    row = {}
                    for exp_label in sens.expense_levels:
                        target = f"Rev {rev_label} / Exp {exp_label}"
                        for case in sens.cases:
                            if case.label == target:
                                row[f"Exp {exp_label}"] = case.dscr if case.dscr is not None else 0.0
                                break
                    dscr_rows.append(row)

                dscr_df = pd.DataFrame(
                    dscr_rows,
                    index=[f"Rev {lbl}" for lbl in sens.revenue_levels],
                )
                styled_dscr = _style_heatmap(dscr_df, "{:.2f}x", 0.5, 2.0)
                st.dataframe(styled_dscr, use_container_width=True)

            # ── Seasonal breakdown ──
            if sens.peak_months_revenue_pct > 0:
                with st.expander("Seasonal Revenue Breakdown"):
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.metric(
                            "Peak 3-Month Share",
                            f"{sens.peak_months_revenue_pct:.0%}",
                        )
                    with sc2:
                        st.metric(
                            "Off-Peak Norm. Revenue",
                            f"${sens.off_peak_normalized_annual:,.0f}",
                        )
                    with sc3:
                        base_rev = s_metrics.annual_gross_revenue
                        prem = base_rev - sens.off_peak_normalized_annual
                        st.metric(
                            "Seasonal Premium",
                            f"${prem:,.0f}",
                            help="Revenue attributable to above-median seasonal pricing",
                        )

st.divider()

# STR Comps
st.subheader("STR Competitive Set")
if result.str_comps:
    comp_rows = []
    for c in result.str_comps:
        comp_rows.append(
            {
                "Platform": c.platform.title(),
                "Title": c.title[:50],
                "Beds": c.beds,
                "Rate (Avg)": c.nightly_rate_avg,
                "Revenue Est.": c.annual_revenue_est or 0,
                "Reviews": c.review_count,
                "Score": c.review_score or 0,
                "Top 10%": "Yes" if c.is_top_performer else "",
                "Distance": f"{c.distance_miles:.1f} mi",
            }
        )
    st.dataframe(
        pd.DataFrame(comp_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rate (Avg)": st.column_config.NumberColumn(format="$%.0f"),
            "Revenue Est.": st.column_config.NumberColumn(format="$%d"),
        },
    )
else:
    st.info("No STR comps available.")

# Report links
st.divider()
st.subheader("Reports")
link_cols = st.columns(3)
with link_cols[0]:
    if result.sheet_url:
        st.link_button("Open Financial Report", result.sheet_url)
    else:
        st.info("Financial report not generated for this property")
with link_cols[1]:
    if result.scope_doc_url:
        st.link_button("Open Scope of Work", result.scope_doc_url)
    else:
        st.info("Scope of work not generated for this property")
with link_cols[2]:
    if result.marketing_doc_url:
        st.link_button("Open Marketing Plan", result.marketing_doc_url)
    else:
        st.info("Marketing plan not generated for this property")
