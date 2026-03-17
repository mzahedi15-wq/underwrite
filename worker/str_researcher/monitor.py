"""CLI entry point for continuous property monitoring.

Usage:
    python -m str_researcher.monitor                           # Continuous loop
    python -m str_researcher.monitor --once                    # Single cycle
    python -m str_researcher.monitor --region smoky-mountains  # One region
    python -m str_researcher.monitor --add "Smoky Mountains" 35.65 -83.50
    python -m str_researcher.monitor --list
    python -m str_researcher.monitor --summary
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from str_researcher.monitoring.db import MonitorDB
from str_researcher.monitoring.service import MonitorService
from str_researcher.utils.logging import get_logger

logger = get_logger("monitor_cli")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="STR Researcher — Continuous Property Monitor"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single monitoring cycle then exit.",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="Only check this specific region (by slug ID).",
    )
    parser.add_argument(
        "--add",
        nargs=3,
        metavar=("NAME", "LAT", "LNG"),
        help='Add a region to monitor. E.g., --add "Smoky Mountains" 35.65 -83.50',
    )
    parser.add_argument(
        "--remove",
        type=str,
        default=None,
        metavar="REGION_ID",
        help="Remove a monitored region by slug ID.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_regions",
        help="List all monitored regions.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print database summary statistics.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=6.0,
        help="Check interval in hours for --add (default: 6).",
    )
    parser.add_argument(
        "--cycle-sleep",
        type=int,
        default=300,
        help="Seconds to sleep between monitoring cycles in continuous mode (default: 300).",
    )

    args = parser.parse_args()

    with MonitorDB() as db:
        service = MonitorService(db, cycle_sleep_seconds=args.cycle_sleep)

        # --add
        if args.add:
            name, lat_str, lng_str = args.add
            try:
                lat = float(lat_str)
                lng = float(lng_str)
            except ValueError:
                print(f"Error: LAT and LNG must be numbers, got {lat_str} {lng_str}")
                sys.exit(1)
            region_id = service.add_region(
                name, lat, lng, check_interval_hours=args.interval
            )
            print(f"Added region: {name} (id={region_id})")
            return

        # --remove
        if args.remove:
            db.delete_region(args.remove)
            print(f"Removed region: {args.remove}")
            return

        # --list
        if args.list_regions:
            regions = db.list_regions()
            if not regions:
                print("No monitored regions. Use --add to add one.")
                return
            print(f"\n{'ID':<25s} {'Name':<30s} {'Enabled':<8s} {'Last Check':<22s} {'Properties'}")
            print("-" * 100)
            for r in regions:
                last = r.get("last_check_at") or "never"
                if last != "never":
                    last = last[:19]
                enabled = "Yes" if r.get("enabled") else "No"
                print(
                    f"{r['region_id']:<25s} "
                    f"{r['name']:<30s} "
                    f"{enabled:<8s} "
                    f"{last:<22s} "
                    f"{r.get('property_count', 0)}"
                )
            return

        # --summary
        if args.summary:
            s = db.summary()
            print("\nMonitor Database Summary:")
            print(f"  Regions:             {s['regions']}")
            print(f"  Tracked Properties:  {s['tracked_properties']}")
            print(f"  New (unseen):        {s['new_properties']}")
            print(f"  Analysis Snapshots:  {s['analysis_snapshots']}")
            print(f"  Monitor Runs:        {s['monitor_runs']}")
            return

        # --once / continuous
        if args.once:
            logger.info("Running single monitoring cycle...")
            summary = asyncio.run(service.run_once(region_id=args.region))
            print(f"\nCycle complete: {json.dumps(summary, indent=2)}")
        else:
            if not db.list_regions():
                print(
                    "No monitored regions configured.\n"
                    'Add one first: python -m str_researcher.monitor --add "Region Name" LAT LNG'
                )
                sys.exit(1)
            logger.info("Starting continuous monitoring...")
            try:
                asyncio.run(service.run_forever())
            except KeyboardInterrupt:
                logger.info("Monitor stopped by user")
                print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
