"""Analyze page - Configure and launch property analysis."""

import asyncio
import threading
import time
from dataclasses import dataclass, field

import streamlit as st

from str_researcher.config import (
    AppConfig,
    CostAssumptions,
    FinancingConfig,
    RegionConfig,
    APIKeys,
    list_available_regions,
    build_config,
)
from str_researcher.monitoring.db import MonitorDB
from str_researcher.monitoring.service import _slugify
from str_researcher.pipeline import AnalysisPipeline
from str_researcher.utils.geocoding import geocode_address


# ── Background pipeline runner ──
# Stores pipeline state in a module-level object so it survives page navigation.
# Streamlit reruns the page script on every interaction, but this object persists
# in the Python process.


@dataclass
class PipelineState:
    """Tracks a running or completed pipeline across page navigations."""

    running: bool = False
    finished: bool = False
    error: str = ""
    results: list = field(default_factory=list)
    log: list = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 10
    current_message: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    region_name: str = ""


# Singleton — persists across Streamlit reruns within the same process
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = PipelineState()


def _run_pipeline_in_thread(config: AppConfig, state: PipelineState) -> None:
    """Run the analysis pipeline in a background thread."""

    def progress_cb(step: int, total: int, message: str) -> None:
        state.current_step = step
        state.total_steps = total
        state.current_message = message
        elapsed = time.time() - state.start_time
        mins, secs = divmod(int(elapsed), 60)
        state.log.append(f"{mins:02d}:{secs:02d} — {message}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        pipeline = AnalysisPipeline(config)
        results = loop.run_until_complete(pipeline.run(progress_cb=progress_cb))
        state.results = results

        # Persist results to monitor DB so they survive page refreshes
        if results:
            try:
                region_id = _slugify(config.region.name)
                with MonitorDB() as db:
                    # Ensure region exists in DB
                    db.upsert_region(
                        region_id=region_id,
                        name=config.region.name,
                        config_json=config.region.model_dump_json(),
                    )
                    run_id = db.start_run(region_id)
                    seen = set()
                    for result in results:
                        db.upsert_property(result, region_id, run_id)
                        seen.add(result.property.address)
                    db.mark_delisted(region_id, seen)
                    db.update_region_after_check(region_id, len(results))
                    db.finish_run(
                        run_id,
                        status="completed",
                        stats={"total": len(results), "source": "analyze_page"},
                    )
                progress_cb(10, 10, f"Results saved — {len(results)} properties persisted to database")
            except Exception as db_err:
                import traceback as _tb
                progress_cb(10, 10, f"DB save warning: {db_err}")
    except Exception as e:
        import traceback

        state.error = f"{e}\n\n{traceback.format_exc()}"
    finally:
        loop.close()
        state.running = False
        state.finished = True
        state.end_time = time.time()


# ── Session state init ──
if "results" not in st.session_state:
    st.session_state.results = None


state: PipelineState = st.session_state.pipeline_state

# ── If pipeline is running, show progress and auto-refresh ──
if state.running:
    st.title("Analysis in Progress")

    elapsed = time.time() - state.start_time
    mins, secs = divmod(int(elapsed), 60)

    st.info(
        f"Analyzing **{state.region_name}**. "
        "This typically takes **10-15 minutes**. "
        "You can navigate to other pages — the analysis will keep running."
    )

    pct = state.current_step / state.total_steps if state.total_steps else 0
    st.progress(pct, text=f"Step {state.current_step}/{state.total_steps}")
    st.markdown(f"**Elapsed:** {mins}m {secs:02d}s")
    st.markdown(f"**{state.current_message}**")

    # Show recent log
    if state.log:
        st.caption("Activity log")
        st.code("\n".join(state.log[-10:]), language=None)

    # Auto-refresh every 3 seconds
    time.sleep(3)
    st.rerun()

# ── If pipeline just finished, show results ──
if state.finished:
    elapsed = state.end_time - state.start_time
    mins, secs = divmod(int(elapsed), 60)

    if state.error:
        st.error(f"Pipeline failed after {mins}m {secs:02d}s")
        st.code(state.error)
    elif state.results:
        st.session_state.results = state.results
        st.success(
            f"Analysis complete! **{len(state.results)} properties** analyzed in "
            f"**{mins}m {secs:02d}s**. "
            "Navigate to the **Rankings** page to view results."
        )
    else:
        st.warning("Analysis completed but no properties were found.")

    # Show full log in expander
    if state.log:
        with st.expander("Full activity log", expanded=False):
            st.code("\n".join(state.log), language=None)

    # Reset button
    if st.button("Start New Analysis"):
        st.session_state.pipeline_state = PipelineState()
        st.rerun()

    if state.results:
        st.stop()


# ── Normal page: region input + config ──

st.title("Analyze Region")

st.header("Region")

region_input = st.text_input(
    "Enter a region to analyze",
    placeholder="e.g., Gatlinburg TN, Joshua Tree CA, Smoky Mountains, Lake Tahoe",
    help="City, county, neighborhood, or point of interest. We'll automatically find the area.",
)

# Check for saved regions too
available_regions = list_available_regions()
if available_regions:
    with st.expander("Or load a saved region"):
        selected_region = st.selectbox("Saved regions", available_regions)
        if st.button("Load"):
            try:
                config = build_config(selected_region)
                st.session_state["_loaded_region"] = config.region
                st.rerun()
            except Exception as e:
                st.error(f"Error loading region: {e}")

# Resolve the region — text input always takes priority
region = None

if region_input:
    st.session_state.pop("_loaded_region", None)
    coords = geocode_address(region_input)
    if coords:
        lat, lng = coords
        st.success(f"Found: {region_input} ({lat:.4f}, {lng:.4f})")
        region = RegionConfig(
            name=region_input,
            center_lat=lat,
            center_lng=lng,
        )
    else:
        st.error(
            f"Could not find **{region_input}**. "
            "Try a more specific name like 'Gatlinburg, TN' or 'Big Bear Lake, CA'."
        )
elif "_loaded_region" in st.session_state:
    region = st.session_state["_loaded_region"]

if not region and not region_input:
    st.info("Enter a region above to get started.")
    st.stop()

if not region:
    st.stop()

# --- Optional Filters (collapsed by default) ---
with st.expander("Filters & search criteria", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        min_price = st.number_input("Min Price ($)", value=region.min_price, step=25000)
        max_price = st.number_input("Max Price ($)", value=region.max_price, step=25000)
        radius = st.number_input(
            "Search Radius (miles)", value=region.radius_miles, min_value=1.0, max_value=100.0
        )
    with col_b:
        min_beds = st.number_input("Min Beds", value=region.min_beds, min_value=1, max_value=20)
        max_beds = st.number_input("Max Beds", value=region.max_beds, min_value=1, max_value=20)

    region = region.model_copy(
        update={
            "min_price": min_price,
            "max_price": max_price,
            "radius_miles": radius,
            "min_beds": min_beds,
            "max_beds": max_beds,
        }
    )

# --- Financing (collapsed) ---
with st.expander("Financing assumptions", expanded=False):
    fin_col1, fin_col2, fin_col3 = st.columns(3)
    with fin_col1:
        st.subheader("Conventional")
        conv_down = st.slider("Down Payment %", 5, 50, 20, key="conv_down") / 100
        conv_rate = st.slider("Interest Rate %", 3.0, 12.0, 7.0, 0.25, key="conv_rate") / 100
    with fin_col2:
        st.subheader("DSCR")
        dscr_down = st.slider("Down Payment %", 5, 50, 25, key="dscr_down") / 100
        dscr_rate = st.slider("Interest Rate %", 3.0, 12.0, 8.0, 0.25, key="dscr_rate") / 100
    with fin_col3:
        st.subheader("General")
        closing_cost_pct = (
            st.slider("Closing Cost %", 1.0, 6.0, 3.0, 0.5, key="closing") / 100
        )

financing = FinancingConfig(
    conventional_down_pct=conv_down,
    conventional_rate=conv_rate,
    dscr_down_pct=dscr_down,
    dscr_rate=dscr_rate,
    closing_cost_pct=closing_cost_pct,
)

# --- Cost Assumptions (collapsed) ---
with st.expander("Cost assumptions", expanded=False):
    cost_col1, cost_col2 = st.columns(2)
    with cost_col1:
        mgmt_fee = st.slider("Management Fee %", 0, 40, 20) / 100
        maint_pct = st.slider("Maintenance %", 0, 15, 5) / 100
        platform_fee = st.slider("Platform Fee %", 0, 10, 3) / 100
        cleaning = st.number_input("Cleaning per turn ($)", value=150, step=25)
    with cost_col2:
        insurance = st.number_input("Annual Insurance ($)", value=2400, step=100)
        utilities = st.number_input("Monthly Utilities ($)", value=300, step=25)
        furnishing = st.number_input("Furnishing per Bedroom ($)", value=5000, step=500)
        tax_rate = st.number_input("Property Tax Rate %", value=1.0, step=0.1) / 100

costs = CostAssumptions(
    management_fee_pct=mgmt_fee,
    maintenance_pct=maint_pct,
    platform_fee_pct=platform_fee,
    cleaning_per_turn=cleaning,
    insurance_annual=insurance,
    utilities_monthly=utilities,
    furnishing_per_bed=furnishing,
    property_tax_rate=tax_rate,
)

# --- Analysis Settings (collapsed) ---
with st.expander("Analysis settings", expanded=False):
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        max_listings = st.number_input(
            "Max Listings to Analyze", value=50, min_value=5, max_value=200
        )
        top_n = st.number_input(
            "Full Reports for Top N Properties", value=5, min_value=1, max_value=20
        )
    with col_s2:
        # Only show AirDNA weight slider if user has an API key
        api_keys = APIKeys()
        has_airdna_key = bool(api_keys.airdna_api_key and api_keys.airdna_api_key != "your_airdna_api_key_here")
        if has_airdna_key:
            airdna_weight = st.slider("AirDNA Revenue Weight %", 0, 100, 50) / 100
            comp_weight = 1.0 - airdna_weight
            st.metric("Comp Revenue Weight %", f"{comp_weight * 100:.0f}%")
        else:
            airdna_weight = 0.0
            comp_weight = 1.0
            st.info("Revenue estimates based on Airbnb/VRBO comps. Add an AirDNA API key in Settings to enable dual estimation.")

# --- Run Analysis ---
st.divider()

if st.button("Run Analysis", type="primary", disabled=state.running):
    full_config = AppConfig(
        region=region,
        financing=financing,
        costs=costs,
        max_listings_to_analyze=max_listings,
        top_n_for_full_reports=top_n,
        revenue_blend_airdna_weight=airdna_weight,
        revenue_blend_comp_weight=comp_weight,
    )

    # Reset state and launch background thread
    new_state = PipelineState(
        running=True,
        start_time=time.time(),
        region_name=region.name,
    )
    st.session_state.pipeline_state = new_state
    st.session_state.pop("_loaded_region", None)

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(full_config, new_state),
        daemon=True,
    )
    thread.start()

    st.rerun()
