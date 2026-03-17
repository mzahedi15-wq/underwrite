"""Monitor Dashboard — track regions, view new properties, price changes."""

import json
import threading
import asyncio
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from str_researcher.monitoring.db import MonitorDB
from str_researcher.monitoring.service import MonitorService, _slugify
from str_researcher.config import RegionConfig, APIKeys
from str_researcher.utils.geocoding import geocode_address


st.title("Property Monitor")


# ── DB connection (cached for session) ──
@st.cache_resource
def _get_db() -> MonitorDB:
    db = MonitorDB()
    db.open()
    return db


db = _get_db()


# ── Add Region Section ──
st.header("Monitored Regions")

with st.expander("Add a new region to monitor"):
    new_region = st.text_input(
        "Region name",
        placeholder="e.g., Gatlinburg TN, Joshua Tree CA",
        key="monitor_region_input",
    )
    interval = st.slider(
        "Check interval (hours)", 1, 24, 6, key="monitor_interval"
    )

    if st.button("Add Region", type="primary") and new_region:
        coords = geocode_address(new_region)
        if coords:
            lat, lng = coords
            service = MonitorService(db)
            region_id = service.add_region(
                new_region, lat, lng, check_interval_hours=interval
            )
            st.success(f"Added **{new_region}** (id: {region_id})")
            st.rerun()
        else:
            st.error(f"Could not geocode '{new_region}'. Try a more specific name.")


# ── Region Cards ──
regions = db.list_regions()

if not regions:
    st.info(
        "No monitored regions yet. Add one above, or from the CLI:\n\n"
        '```\npython -m str_researcher.monitor --add "Gatlinburg TN" 35.71 -83.51\n```'
    )
    st.stop()


for region in regions:
    rid = region["region_id"]
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        with col1:
            st.markdown(f"### {region['name']}")
            last = region.get("last_check_at")
            if last:
                st.caption(f"Last checked: {last[:19]}")
            else:
                st.caption("Never checked")

        with col2:
            st.metric("Properties", region.get("property_count", 0))

        with col3:
            new_count = db.get_new_property_count(rid)
            st.metric("New", new_count)

        with col4:
            enabled = bool(region.get("enabled", 1))
            btn_cols = st.columns(3)
            with btn_cols[0]:
                if enabled:
                    if st.button("Pause", key=f"pause_{rid}"):
                        db.set_region_enabled(rid, False)
                        st.rerun()
                else:
                    if st.button("Resume", key=f"resume_{rid}"):
                        db.set_region_enabled(rid, True)
                        st.rerun()
            with btn_cols[1]:
                if st.button("Run Now", key=f"run_{rid}"):
                    st.session_state[f"_run_region_{rid}"] = True
                    st.rerun()
            with btn_cols[2]:
                if st.button("Remove", key=f"del_{rid}"):
                    db.delete_region(rid)
                    st.rerun()

    # Handle "Run Now" — run pipeline in background thread
    if st.session_state.get(f"_run_region_{rid}"):
        st.session_state.pop(f"_run_region_{rid}", None)

        status_placeholder = st.empty()
        status_placeholder.info(f"Running analysis for **{region['name']}**... This may take 10-15 minutes.")

        def _run_monitor(region_id: str) -> None:
            try:
                with MonitorDB() as thread_db:
                    svc = MonitorService(thread_db)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(svc.run_once(region_id=region_id))
                    loop.close()
                st.session_state[f"_run_done_{region_id}"] = True
            except Exception as e:
                st.session_state[f"_run_error_{region_id}"] = str(e)

        thread = threading.Thread(
            target=_run_monitor, args=(rid,), daemon=True
        )
        thread.start()

    # Show run completion
    if st.session_state.get(f"_run_done_{rid}"):
        st.session_state.pop(f"_run_done_{rid}", None)
        st.success(f"Analysis complete for **{region['name']}**!")
        st.rerun()
    if st.session_state.get(f"_run_error_{rid}"):
        err = st.session_state.pop(f"_run_error_{rid}")
        st.error(f"Analysis failed: {err}")

st.divider()

# ── New Properties ──
st.header("New Properties")
st.caption("Properties discovered since your last review.")

new_props = db.get_properties(is_new=True, order_by="investment_score DESC")
if new_props:
    new_rows = []
    for p in new_props:
        new_rows.append({
            "Address": p["raw_address"],
            "City": p.get("city", ""),
            "Beds": p["beds"],
            "Price": p["current_price"],
            "Score": p["investment_score"],
            "First Seen": p["first_seen_at"][:10] if p["first_seen_at"] else "",
            "property_id": p["property_id"],
            "region_id": p["region_id"],
        })

    new_df = pd.DataFrame(new_rows)
    st.dataframe(
        new_df.drop(columns=["property_id", "region_id"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%d"),
            "Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # Mark as seen button
    col_mark1, col_mark2 = st.columns([1, 4])
    with col_mark1:
        if st.button("Mark All as Seen"):
            for region in regions:
                db.mark_properties_seen(region["region_id"])
            st.rerun()

    # View detail
    if new_rows:
        selected_new = st.selectbox(
            "View property detail",
            [r["Address"] for r in new_rows],
            key="new_prop_select",
        )
        if st.button("View Detail", key="view_new_detail"):
            for row in new_rows:
                if row["Address"] == selected_new:
                    result = db.get_latest_snapshot(row["property_id"])
                    if result:
                        st.session_state.results = [result]
                        st.session_state.selected_property_index = 0
                        st.switch_page("pages/3_property_detail.py")
                    else:
                        st.error("No analysis snapshot found for this property.")
                    break
else:
    st.success("No new properties — you're all caught up!")

st.divider()

# ── Price Changes ──
st.header("Price Changes")
price_changes = db.get_price_changes(limit=30)
if price_changes:
    pc_rows = []
    for pc in price_changes:
        delta = pc["current_price"] - pc["old_price"]
        pc_rows.append({
            "Address": pc["raw_address"],
            "Beds": pc["beds"],
            "Old Price": pc["old_price"],
            "New Price": pc["current_price"],
            "Change": delta,
            "Change %": f"{delta / pc['old_price']:.1%}" if pc["old_price"] else "N/A",
            "Score": pc["investment_score"],
            "Date": pc["observed_at"][:10] if pc["observed_at"] else "",
        })
    st.dataframe(
        pd.DataFrame(pc_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Old Price": st.column_config.NumberColumn(format="$%d"),
            "New Price": st.column_config.NumberColumn(format="$%d"),
            "Change": st.column_config.NumberColumn(format="$%d"),
            "Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )
else:
    st.info("No price changes detected yet.")

st.divider()

# ── All Properties Browser ──
st.header("All Tracked Properties")

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    filter_region = st.selectbox(
        "Region",
        ["All"] + [r["name"] for r in regions],
        key="prop_filter_region",
    )
with filter_col2:
    filter_status = st.selectbox(
        "Status",
        ["All", "new", "active", "price_changed", "delisted"],
        key="prop_filter_status",
    )

query_region = None
if filter_region != "All":
    for r in regions:
        if r["name"] == filter_region:
            query_region = r["region_id"]
            break

query_status = filter_status if filter_status != "All" else None

all_props = db.get_properties(
    region_id=query_region,
    status=query_status,
    order_by="investment_score DESC",
    limit=200,
)

if all_props:
    all_rows = []
    for p in all_props:
        all_rows.append({
            "Address": p["raw_address"],
            "City": p.get("city", ""),
            "Beds": p["beds"],
            "Price": p["current_price"],
            "Status": p["status"],
            "Score": p["investment_score"],
            "First Seen": p["first_seen_at"][:10] if p.get("first_seen_at") else "",
            "Last Seen": p["last_seen_at"][:10] if p.get("last_seen_at") else "",
            "property_id": p["property_id"],
        })

    all_df = pd.DataFrame(all_rows)
    st.dataframe(
        all_df.drop(columns=["property_id"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%d"),
            "Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # View detail
    selected_prop = st.selectbox(
        "View property detail",
        [r["Address"] for r in all_rows],
        key="all_prop_select",
    )
    if st.button("View Detail", key="view_all_detail"):
        for row in all_rows:
            if row["Address"] == selected_prop:
                result = db.get_latest_snapshot(row["property_id"])
                if result:
                    st.session_state.results = [result]
                    st.session_state.selected_property_index = 0
                    st.switch_page("pages/3_property_detail.py")
                else:
                    st.error("No analysis snapshot found for this property.")
                break
else:
    st.info("No properties match the selected filters.")

st.divider()

# ── Run History ──
with st.expander("Run History"):
    runs = db.get_runs(limit=20)
    if runs:
        run_rows = []
        for run in runs:
            stats = json.loads(run.get("stats_json", "{}"))
            run_rows.append({
                "Region": run["region_id"],
                "Status": run["status"],
                "Started": run["started_at"][:19] if run["started_at"] else "",
                "Finished": run["finished_at"][:19] if run.get("finished_at") else "",
                "New": stats.get("new", 0),
                "Price Changes": stats.get("price_changed", 0),
                "Delisted": stats.get("delisted", 0),
                "Total": stats.get("total", 0),
            })
        st.dataframe(pd.DataFrame(run_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No monitor runs recorded yet.")

# ── DB Stats ──
with st.expander("Database Stats"):
    stats = db.summary()
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    with sc1:
        st.metric("Regions", stats["regions"])
    with sc2:
        st.metric("Properties", stats["tracked_properties"])
    with sc3:
        st.metric("New", stats["new_properties"])
    with sc4:
        st.metric("Snapshots", stats["analysis_snapshots"])
    with sc5:
        st.metric("Runs", stats["monitor_runs"])
