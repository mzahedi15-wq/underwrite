"""Background monitoring service — runs the analysis pipeline per region."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

from str_researcher.config import AppConfig, APIKeys, RegionConfig
from str_researcher.monitoring.db import MonitorDB
from str_researcher.pipeline import AnalysisPipeline
from str_researcher.utils.logging import get_logger

logger = get_logger("monitor_service")


def _slugify(name: str) -> str:
    """Convert a region name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class MonitorService:
    """Runs the analysis pipeline for monitored regions.

    Can be used as:
    - service.run_once() — single cycle across all due regions
    - service.run_once(region_id="smoky-mountains") — single region
    - service.run_forever() — continuous loop with sleep between cycles
    """

    def __init__(self, db: MonitorDB, cycle_sleep_seconds: int = 300):
        self._db = db
        self._cycle_sleep = cycle_sleep_seconds

    def add_region(
        self,
        name: str,
        lat: float,
        lng: float,
        check_interval_hours: float = 6,
        **kwargs,
    ) -> str:
        """Add a new region to monitor. Returns the region_id slug."""
        region_id = _slugify(name)
        config = RegionConfig(
            name=name,
            center_lat=lat,
            center_lng=lng,
            **kwargs,
        )
        import json
        self._db.upsert_region(
            region_id=region_id,
            name=name,
            config_json=config.model_dump_json(),
            check_interval_hours=check_interval_hours,
        )
        logger.info("Added region '%s' (id=%s)", name, region_id)
        return region_id

    async def run_once(self, region_id: Optional[str] = None) -> dict:
        """Run a single monitoring cycle.

        If region_id is given, only check that region.
        Otherwise, check all regions that are due.

        Returns a summary dict: {region_id: {new, updated, delisted, total}}
        """
        if region_id:
            region = self._db.get_region(region_id)
            if not region:
                logger.error("Region '%s' not found", region_id)
                return {}
            regions_to_check = [region]
        else:
            regions_to_check = self._db.regions_due_for_check()
            if not regions_to_check:
                logger.info("No regions due for checking")
                return {}

        summary = {}
        for region_row in regions_to_check:
            rid = region_row["region_id"]
            rname = region_row["name"]
            logger.info("Checking region: %s (%s)", rname, rid)

            try:
                stats = await self._check_region(region_row)
                summary[rid] = stats
                logger.info(
                    "Region %s: %d new, %d price changes, %d delisted, %d total",
                    rname,
                    stats.get("new", 0),
                    stats.get("price_changed", 0),
                    stats.get("delisted", 0),
                    stats.get("total", 0),
                )
            except Exception as e:
                logger.error("Failed to check region %s: %s", rname, e)
                summary[rid] = {"error": str(e)}

        return summary

    async def run_forever(self) -> None:
        """Run continuous monitoring loop."""
        logger.info("Starting continuous monitoring (cycle sleep=%ds)", self._cycle_sleep)
        while True:
            try:
                summary = await self.run_once()
                if summary:
                    logger.info("Cycle complete: %s", summary)
                else:
                    logger.info("No regions due — sleeping %ds", self._cycle_sleep)
            except Exception as e:
                logger.error("Monitoring cycle error: %s", e)

            await asyncio.sleep(self._cycle_sleep)

    async def _check_region(self, region_row: dict) -> dict:
        """Run the pipeline for one region and update the database."""
        region_id = region_row["region_id"]

        # Parse stored config
        region_config = RegionConfig.model_validate_json(region_row["config_json"])

        # Build a lightweight AppConfig (skip reports and AI analysis)
        app_config = AppConfig(
            region=region_config,
            api_keys=APIKeys(),
            top_n_for_full_reports=0,  # Skip Google Sheets/Docs
            max_listings_to_analyze=100,
        )
        # Clear anthropic key to skip AI analysis
        app_config.api_keys.anthropic_api_key = ""

        # Start a monitor run
        run_id = self._db.start_run(region_id)

        try:
            # Run the pipeline
            pipeline = AnalysisPipeline(app_config)
            results = await pipeline.run()

            # Track changes
            stats = {"new": 0, "price_changed": 0, "updated": 0, "unchanged": 0}
            seen_addresses = set()

            for result in results:
                seen_addresses.add(result.property.address)
                _pid, change_type = self._db.upsert_property(
                    result, region_id, run_id
                )
                if change_type in stats:
                    stats[change_type] += 1

            # Mark delisted
            delisted = self._db.mark_delisted(region_id, seen_addresses)
            stats["delisted"] = delisted
            stats["total"] = len(results)

            # Update region timestamps
            self._db.update_region_after_check(region_id, len(results))

            # Finish the run
            self._db.finish_run(run_id, status="completed", stats=stats)

            return stats

        except Exception as e:
            self._db.finish_run(run_id, status="failed", stats={"error": str(e)})
            raise
