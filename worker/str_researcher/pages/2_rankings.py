"""Rankings page - Property ranking dashboard."""

import threading
import time

import streamlit as st
import pandas as pd

from str_researcher.monitoring.db import MonitorDB


st.title("Property Rankings")

# Try session_state first, then fall back to the persistent database
if not st.session_state.get("results"):
    try:
        with MonitorDB() as db:
            db_results = db.get_all_latest_results(limit=200)
            if db_results:
                st.session_state.results = db_results
                st.info(
                    f"Loaded **{len(db_results)} properties** from previous analyses. "
                    "Run a new analysis from the **Analyze** page to refresh."
                )
    except Exception:
        pass  # DB doesn't exist yet or other issue — fine, show empty state

if not st.session_state.get("results"):
    st.info("No analysis results yet. Go to the **Analyze** page to run an analysis.")
    st.stop()

results = st.session_state.results

# Build rankings DataFrame
rows = []
for r in results:
    best_scenario = max(
        r.investment_metrics.values(),
        key=lambda m: m.cash_on_cash_return,
        default=None,
    )
    rows.append(
        {
            "Rank": r.investment_rank,
            "Address": r.property.address,
            "City": r.property.city,
            "Price": r.property.list_price,
            "Beds": r.property.beds,
            "Baths": r.property.baths,
            "Sqft": r.property.sqft or "N/A",
            "Revenue (Moderate)": r.revenue_estimate.moderate_revenue,
            "CoC Return": (
                f"{best_scenario.cash_on_cash_return:.1%}" if best_scenario else "N/A"
            ),
            "Cap Rate": f"{best_scenario.cap_rate:.1%}" if best_scenario else "N/A",
            "Score": f"{r.investment_score:.1f}",
            "Listing": r.property.source_url or "",
            "Sheet": r.sheet_url or "",
            "Scope": r.scope_doc_url or "",
            "Marketing": r.marketing_doc_url or "",
        }
    )

df = pd.DataFrame(rows)

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Properties Analyzed", len(results))
with col2:
    top_score = max(r.investment_score for r in results) if results else 0
    st.metric("Top Investment Score", f"{top_score:.1f}")
with col3:
    avg_revenue = (
        sum(r.revenue_estimate.moderate_revenue for r in results) / len(results)
        if results
        else 0
    )
    st.metric("Avg Projected Revenue", f"${avg_revenue:,.0f}")
with col4:
    full_reports = sum(1 for r in results if r.sheet_url)
    st.metric("Full Reports Generated", full_reports)

st.divider()

# Rankings table
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Price": st.column_config.NumberColumn(format="$%d"),
        "Revenue (Moderate)": st.column_config.NumberColumn(format="$%d"),
        "Listing": st.column_config.LinkColumn("Listing"),
        "Sheet": st.column_config.LinkColumn("Financial Report"),
        "Scope": st.column_config.LinkColumn("Scope of Work"),
        "Marketing": st.column_config.LinkColumn("Marketing Plan"),
    },
)

# ── Generate Reports ──
st.divider()
st.subheader("Generate Financial Reports")

# Check how many are missing reports
missing_reports = [r for r in results if not r.sheet_url]

if not missing_reports:
    st.success("All properties have financial reports generated.")
else:
    st.info(
        f"**{len(missing_reports)}** of {len(results)} properties are missing "
        "Google Sheets financial reports."
    )

    report_col1, report_col2 = st.columns(2)
    with report_col1:
        top_n_reports = st.number_input(
            "Generate reports for top N properties",
            min_value=1,
            max_value=len(results),
            value=min(5, len(results)),
            help="Properties are sorted by investment score. Reports include "
            "financial sheets, scope of work docs, and marketing plan docs.",
        )
    with report_col2:
        include_docs = st.checkbox(
            "Include Scope of Work & Marketing Plan docs",
            value=True,
            help="Generate Google Docs in addition to Google Sheets. "
            "Requires AI-generated content from the analysis step.",
        )

    # Track report generation state in session_state
    if "report_gen" not in st.session_state:
        st.session_state.report_gen = {
            "running": False,
            "finished": False,
            "error": "",
            "log": [],
            "generated": 0,
            "total": 0,
        }

    rg = st.session_state.report_gen

    if rg["running"]:
        st.warning("Report generation in progress...")
        pct = rg["generated"] / rg["total"] if rg["total"] else 0
        st.progress(pct, text=f"{rg['generated']}/{rg['total']} reports generated")
        if rg["log"]:
            st.code("\n".join(rg["log"][-8:]), language=None)
        time.sleep(2)
        st.rerun()

    elif rg["finished"]:
        if rg["error"]:
            st.error(f"Report generation failed: {rg['error']}")
        else:
            st.success(
                f"Generated reports for **{rg['generated']}** properties. "
                "Refresh the page to see updated links."
            )
        if rg["log"]:
            with st.expander("Generation log", expanded=False):
                st.code("\n".join(rg["log"]), language=None)
        if st.button("Clear & Reload"):
            st.session_state.report_gen = {
                "running": False, "finished": False, "error": "",
                "log": [], "generated": 0, "total": 0,
            }
            # Force reload results from DB to pick up new URLs
            st.session_state.pop("results", None)
            st.rerun()

    elif st.button("Generate Reports", type="primary"):
        # Launch report generation in background thread
        from str_researcher.config import APIKeys

        api_keys = APIKeys()
        creds_path = api_keys.google_credentials_path

        # Take top N results sorted by score
        sorted_results = sorted(results, key=lambda r: r.investment_score, reverse=True)
        target_results = sorted_results[:top_n_reports]

        rg["running"] = True
        rg["finished"] = False
        rg["error"] = ""
        rg["log"] = []
        rg["generated"] = 0
        rg["total"] = len(target_results)

        def _generate_reports_thread(
            target: list,
            creds_path: str,
            gen_docs: bool,
            state: dict,
        ) -> None:
            """Generate reports in a background thread."""
            try:
                from str_researcher.reporting.google_auth import GoogleAuthManager
                from str_researcher.reporting.sheets import SheetsBuilder
                from str_researcher.reporting.docs import DocsBuilder

                state["log"].append("Authenticating with Google...")
                auth = GoogleAuthManager(creds_path)
                auth.authenticate(interactive=False)

                gc = auth.get_gspread_client()
                sheets = SheetsBuilder(gc)

                docs_builder = None
                if gen_docs:
                    try:
                        docs_service = auth.get_docs_service()
                        drive_service = auth.get_drive_service()
                        docs_builder = DocsBuilder(docs_service, drive_service)
                    except Exception as e:
                        state["log"].append(f"Google Docs init failed: {e}")

                for i, result in enumerate(target):
                    addr = result.property.address
                    state["log"].append(f"[{i + 1}/{len(target)}] {addr}...")

                    # Google Sheet
                    if not result.sheet_url:
                        try:
                            result.sheet_url = sheets.create_property_sheet(result)
                            state["log"].append(f"  Sheet created")
                        except Exception as e:
                            state["log"].append(f"  Sheet FAILED: {e}")

                    # Scope of Work doc
                    if gen_docs and docs_builder and result.scope_of_work and not result.scope_doc_url:
                        try:
                            result.scope_doc_url = docs_builder.create_scope_of_work_doc(result)
                            state["log"].append(f"  Scope doc created")
                        except Exception as e:
                            state["log"].append(f"  Scope doc FAILED: {e}")

                    # Marketing Plan doc
                    if gen_docs and docs_builder and result.marketing_plan and not result.marketing_doc_url:
                        try:
                            result.marketing_doc_url = docs_builder.create_marketing_plan_doc(result)
                            state["log"].append(f"  Marketing doc created")
                        except Exception as e:
                            state["log"].append(f"  Marketing doc FAILED: {e}")

                    # Persist updated URLs back to DB
                    try:
                        with MonitorDB() as db:
                            prop_id = db.get_property_id_by_address(addr)
                            if prop_id:
                                db.update_latest_snapshot(prop_id, result)
                    except Exception as e:
                        state["log"].append(f"  DB update warning: {e}")

                    state["generated"] = i + 1

                # Master ranking sheet
                try:
                    state["log"].append("Creating master ranking sheet...")
                    all_sorted = sorted(target, key=lambda r: r.investment_score, reverse=True)
                    ranking_url = sheets.create_master_ranking(all_sorted)
                    state["log"].append(f"Master ranking: {ranking_url}")
                except Exception as e:
                    state["log"].append(f"Master ranking FAILED: {e}")

                state["log"].append("Done!")

            except Exception as e:
                import traceback
                state["error"] = f"{e}\n\n{traceback.format_exc()}"
                state["log"].append(f"FATAL: {e}")
            finally:
                state["running"] = False
                state["finished"] = True

        thread = threading.Thread(
            target=_generate_reports_thread,
            args=(target_results, creds_path, include_docs, rg),
            daemon=True,
        )
        thread.start()
        st.rerun()


# Property selection for detail view
st.divider()
st.subheader("View Property Detail")
if rows:
    selected_address = st.selectbox(
        "Select a property",
        [r["Address"] for r in rows],
    )
    if st.button("View Detail"):
        # Store selected property index in session state
        for i, r in enumerate(results):
            if r.property.address == selected_address:
                st.session_state.selected_property_index = i
                st.switch_page("pages/3_property_detail.py")
                break
