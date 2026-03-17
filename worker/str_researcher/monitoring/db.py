"""SQLite persistence layer for continuous property monitoring.

Stores tracked properties, analysis snapshots, price history, and monitor
run metadata.  Designed to be used from both the Streamlit dashboard (sync
helper wrappers) and the async background monitor service.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from str_researcher.models.report import AnalysisResult
from str_researcher.utils.geocoding import normalize_address
from str_researcher.utils.logging import get_logger

logger = get_logger("monitor_db")

_CACHE_DIR = Path(__file__).parent.parent.parent.parent / ".cache"
DEFAULT_DB_PATH = _CACHE_DIR / "str_monitor.db"

# How many analysis snapshots to keep per property
MAX_SNAPSHOTS_PER_PROPERTY = 3


class MonitorDB:
    """Synchronous SQLite persistence for the monitoring subsystem.

    All writes are auto-committed.  The class can be used as a context
    manager (``with MonitorDB() as db: ...``) or by calling ``open()`` /
    ``close()`` manually.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ── lifecycle ──

    def open(self) -> "MonitorDB":
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        logger.info("MonitorDB opened at %s", self._db_path)
        return self

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "MonitorDB":
        return self.open()

    def __exit__(self, *args) -> None:
        self.close()

    # ── schema ──

    def _init_schema(self) -> None:
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS monitored_regions (
                region_id       TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                config_json     TEXT NOT NULL,
                check_interval_hours REAL DEFAULT 6,
                enabled         INTEGER DEFAULT 1,
                last_check_at   TEXT,
                next_check_at   TEXT,
                property_count  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tracked_properties (
                property_id     TEXT PRIMARY KEY,
                region_id       TEXT NOT NULL REFERENCES monitored_regions(region_id),
                normalized_address TEXT NOT NULL,
                raw_address     TEXT NOT NULL,
                city            TEXT DEFAULT '',
                state           TEXT DEFAULT '',
                beds            INTEGER DEFAULT 0,
                baths           REAL DEFAULT 0,
                sqft            INTEGER,
                current_price   INTEGER DEFAULT 0,
                original_price  INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'new',
                investment_score REAL DEFAULT 0,
                first_seen_at   TEXT NOT NULL,
                last_seen_at    TEXT NOT NULL,
                is_new          INTEGER DEFAULT 1,
                source_url      TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_tp_region
                ON tracked_properties(region_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tp_norm_addr_region
                ON tracked_properties(normalized_address, region_id);

            CREATE TABLE IF NOT EXISTS analysis_snapshots (
                snapshot_id     TEXT PRIMARY KEY,
                property_id     TEXT NOT NULL REFERENCES tracked_properties(property_id),
                run_id          TEXT,
                analysis_json   TEXT NOT NULL,
                investment_score REAL DEFAULT 0,
                analyzed_at     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_as_property
                ON analysis_snapshots(property_id);

            CREATE TABLE IF NOT EXISTS price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id     TEXT NOT NULL REFERENCES tracked_properties(property_id),
                price           INTEGER NOT NULL,
                observed_at     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ph_property
                ON price_history(property_id);

            CREATE TABLE IF NOT EXISTS monitor_runs (
                run_id          TEXT PRIMARY KEY,
                region_id       TEXT NOT NULL REFERENCES monitored_regions(region_id),
                started_at      TEXT NOT NULL,
                finished_at     TEXT,
                status          TEXT DEFAULT 'running',
                stats_json      TEXT DEFAULT '{}'
            );
            """
        )
        c.commit()

    # ── regions ──

    def upsert_region(
        self,
        region_id: str,
        name: str,
        config_json: str,
        check_interval_hours: float = 6,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO monitored_regions
                (region_id, name, config_json, check_interval_hours)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(region_id) DO UPDATE SET
                name=excluded.name,
                config_json=excluded.config_json,
                check_interval_hours=excluded.check_interval_hours
            """,
            (region_id, name, config_json, check_interval_hours),
        )
        self._conn.commit()

    def list_regions(self) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM monitored_regions ORDER BY name"
        )
        return [dict(r) for r in cur.fetchall()]

    def get_region(self, region_id: str) -> Optional[dict]:
        cur = self._conn.execute(
            "SELECT * FROM monitored_regions WHERE region_id = ?",
            (region_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def delete_region(self, region_id: str) -> None:
        self._conn.execute(
            "DELETE FROM monitored_regions WHERE region_id = ?",
            (region_id,),
        )
        self._conn.commit()

    def set_region_enabled(self, region_id: str, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE monitored_regions SET enabled = ? WHERE region_id = ?",
            (1 if enabled else 0, region_id),
        )
        self._conn.commit()

    def regions_due_for_check(self) -> list[dict]:
        """Return regions that are enabled and past their next_check_at."""
        now = datetime.utcnow().isoformat()
        cur = self._conn.execute(
            """
            SELECT * FROM monitored_regions
            WHERE enabled = 1
              AND (next_check_at IS NULL OR next_check_at <= ?)
            ORDER BY next_check_at
            """,
            (now,),
        )
        return [dict(r) for r in cur.fetchall()]

    def update_region_after_check(
        self, region_id: str, property_count: int
    ) -> None:
        now = datetime.utcnow()
        region = self.get_region(region_id)
        interval = region["check_interval_hours"] if region else 6
        next_check = now + timedelta(hours=interval)
        self._conn.execute(
            """
            UPDATE monitored_regions
            SET last_check_at = ?, next_check_at = ?, property_count = ?
            WHERE region_id = ?
            """,
            (now.isoformat(), next_check.isoformat(), property_count, region_id),
        )
        self._conn.commit()

    # ── properties ──

    def upsert_property(
        self,
        result: AnalysisResult,
        region_id: str,
        run_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """Insert or update a tracked property from an AnalysisResult.

        Returns (property_id, change_type) where change_type is one of:
        'new', 'price_changed', 'updated', 'unchanged'.
        """
        prop = result.property
        norm_addr = normalize_address(prop.address)
        now = datetime.utcnow().isoformat()

        # Check for existing property
        cur = self._conn.execute(
            """
            SELECT property_id, current_price, status
            FROM tracked_properties
            WHERE normalized_address = ? AND region_id = ?
            """,
            (norm_addr, region_id),
        )
        existing = cur.fetchone()

        if existing:
            property_id = existing["property_id"]
            old_price = existing["current_price"]
            change_type = "unchanged"

            updates = {
                "last_seen_at": now,
                "investment_score": result.investment_score,
                "beds": prop.beds,
                "baths": prop.baths,
                "sqft": prop.sqft,
                "source_url": prop.source_url,
            }

            # Detect price change
            if prop.list_price != old_price:
                updates["current_price"] = prop.list_price
                updates["status"] = "price_changed"
                change_type = "price_changed"

                # Record price history
                self._conn.execute(
                    """
                    INSERT INTO price_history (property_id, price, observed_at)
                    VALUES (?, ?, ?)
                    """,
                    (property_id, prop.list_price, now),
                )
            else:
                # If it was delisted and reappears, mark active
                if existing["status"] == "delisted":
                    updates["status"] = "active"
                    change_type = "updated"
                else:
                    updates["status"] = "active"

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [property_id]
            self._conn.execute(
                f"UPDATE tracked_properties SET {set_clause} WHERE property_id = ?",
                vals,
            )
        else:
            # New property
            property_id = str(uuid.uuid4())
            change_type = "new"

            self._conn.execute(
                """
                INSERT INTO tracked_properties
                    (property_id, region_id, normalized_address, raw_address,
                     city, state, beds, baths, sqft,
                     current_price, original_price, status,
                     investment_score, first_seen_at, last_seen_at,
                     is_new, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, 1, ?)
                """,
                (
                    property_id,
                    region_id,
                    norm_addr,
                    prop.address,
                    prop.city,
                    prop.state,
                    prop.beds,
                    prop.baths,
                    prop.sqft,
                    prop.list_price,
                    prop.list_price,
                    result.investment_score,
                    now,
                    now,
                    prop.source_url,
                ),
            )

            # Initial price history entry
            self._conn.execute(
                """
                INSERT INTO price_history (property_id, price, observed_at)
                VALUES (?, ?, ?)
                """,
                (property_id, prop.list_price, now),
            )

        # Save analysis snapshot
        self._save_snapshot(property_id, result, run_id)

        self._conn.commit()
        return property_id, change_type

    def _save_snapshot(
        self,
        property_id: str,
        result: AnalysisResult,
        run_id: Optional[str],
    ) -> None:
        """Save an analysis snapshot, pruning old ones."""
        now = datetime.utcnow().isoformat()
        snapshot_id = str(uuid.uuid4())

        analysis_json = result.model_dump_json()

        self._conn.execute(
            """
            INSERT INTO analysis_snapshots
                (snapshot_id, property_id, run_id, analysis_json,
                 investment_score, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                property_id,
                run_id,
                analysis_json,
                result.investment_score,
                now,
            ),
        )

        # Prune old snapshots — keep only the latest N
        self._conn.execute(
            """
            DELETE FROM analysis_snapshots
            WHERE property_id = ?
              AND snapshot_id NOT IN (
                  SELECT snapshot_id FROM analysis_snapshots
                  WHERE property_id = ?
                  ORDER BY analyzed_at DESC
                  LIMIT ?
              )
            """,
            (property_id, property_id, MAX_SNAPSHOTS_PER_PROPERTY),
        )

    def mark_delisted(self, region_id: str, seen_addresses: set[str]) -> int:
        """Mark properties not in the latest scrape as delisted.

        Returns the number of properties marked delisted.
        """
        # Normalize all seen addresses
        normalized_seen = {normalize_address(a) for a in seen_addresses}

        # Get all active (non-delisted) properties for this region
        cur = self._conn.execute(
            """
            SELECT property_id, normalized_address
            FROM tracked_properties
            WHERE region_id = ? AND status != 'delisted'
            """,
            (region_id,),
        )

        delisted = 0
        now = datetime.utcnow().isoformat()
        for row in cur.fetchall():
            if row["normalized_address"] not in normalized_seen:
                self._conn.execute(
                    """
                    UPDATE tracked_properties
                    SET status = 'delisted', last_seen_at = ?
                    WHERE property_id = ?
                    """,
                    (now, row["property_id"]),
                )
                delisted += 1

        if delisted:
            self._conn.commit()
        return delisted

    def mark_properties_seen(self, region_id: str) -> int:
        """Mark all is_new=1 properties in a region as seen (is_new=0)."""
        cur = self._conn.execute(
            """
            UPDATE tracked_properties
            SET is_new = 0
            WHERE region_id = ? AND is_new = 1
            """,
            (region_id,),
        )
        self._conn.commit()
        return cur.rowcount

    # ── queries ──

    def get_properties(
        self,
        region_id: Optional[str] = None,
        status: Optional[str] = None,
        is_new: Optional[bool] = None,
        order_by: str = "investment_score DESC",
        limit: int = 200,
    ) -> list[dict]:
        """Query tracked properties with optional filters."""
        conditions = []
        params: list = []

        if region_id:
            conditions.append("region_id = ?")
            params.append(region_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if is_new is not None:
            conditions.append("is_new = ?")
            params.append(1 if is_new else 0)

        where = " AND ".join(conditions) if conditions else "1=1"

        cur = self._conn.execute(
            f"""
            SELECT * FROM tracked_properties
            WHERE {where}
            ORDER BY {order_by}
            LIMIT ?
            """,
            params + [limit],
        )
        return [dict(r) for r in cur.fetchall()]

    def get_latest_snapshot(self, property_id: str) -> Optional[AnalysisResult]:
        """Get the most recent AnalysisResult for a property."""
        cur = self._conn.execute(
            """
            SELECT analysis_json FROM analysis_snapshots
            WHERE property_id = ?
            ORDER BY analyzed_at DESC
            LIMIT 1
            """,
            (property_id,),
        )
        row = cur.fetchone()
        if row:
            try:
                return AnalysisResult.model_validate_json(row["analysis_json"])
            except Exception as e:
                logger.error("Failed to deserialize snapshot: %s", e)
        return None

    def update_latest_snapshot(self, property_id: str, result: AnalysisResult) -> bool:
        """Replace the latest snapshot's analysis_json with updated data.

        Used after generating reports to persist the new URLs (sheet_url,
        scope_doc_url, marketing_doc_url) back into the database.
        Returns True if a snapshot was updated.
        """
        cur = self._conn.execute(
            """
            SELECT snapshot_id FROM analysis_snapshots
            WHERE property_id = ?
            ORDER BY analyzed_at DESC
            LIMIT 1
            """,
            (property_id,),
        )
        row = cur.fetchone()
        if not row:
            return False

        self._conn.execute(
            """
            UPDATE analysis_snapshots
            SET analysis_json = ?
            WHERE snapshot_id = ?
            """,
            (result.model_dump_json(), row["snapshot_id"]),
        )
        self._conn.commit()
        return True

    def get_property_id_by_address(self, address: str) -> Optional[str]:
        """Look up property_id by raw or normalized address."""
        norm = normalize_address(address)
        cur = self._conn.execute(
            """
            SELECT property_id FROM tracked_properties
            WHERE normalized_address = ?
            LIMIT 1
            """,
            (norm,),
        )
        row = cur.fetchone()
        return row["property_id"] if row else None

    def get_all_latest_results(
        self,
        region_id: Optional[str] = None,
        limit: int = 200,
    ) -> list[AnalysisResult]:
        """Get the latest AnalysisResult for every tracked property.

        Ordered by investment_score descending.
        """
        if region_id:
            props = self.get_properties(
                region_id=region_id, order_by="investment_score DESC", limit=limit
            )
        else:
            props = self.get_properties(
                order_by="investment_score DESC", limit=limit
            )

        results = []
        for prop in props:
            result = self.get_latest_snapshot(prop["property_id"])
            if result:
                results.append(result)
        return results

    def get_price_history(self, property_id: str) -> list[dict]:
        """Get price history for a property, oldest first."""
        cur = self._conn.execute(
            """
            SELECT price, observed_at FROM price_history
            WHERE property_id = ?
            ORDER BY observed_at ASC
            """,
            (property_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_price_changes(
        self, region_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get recent price changes across all or one region."""
        if region_id:
            cur = self._conn.execute(
                """
                SELECT tp.raw_address, tp.beds, tp.current_price,
                       tp.original_price, tp.investment_score,
                       ph.price AS old_price, ph.observed_at
                FROM tracked_properties tp
                JOIN price_history ph ON tp.property_id = ph.property_id
                WHERE tp.region_id = ? AND tp.status = 'price_changed'
                ORDER BY ph.observed_at DESC
                LIMIT ?
                """,
                (region_id, limit),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT tp.raw_address, tp.beds, tp.current_price,
                       tp.original_price, tp.investment_score,
                       ph.price AS old_price, ph.observed_at
                FROM tracked_properties tp
                JOIN price_history ph ON tp.property_id = ph.property_id
                WHERE tp.status = 'price_changed'
                ORDER BY ph.observed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(r) for r in cur.fetchall()]

    def get_new_property_count(self, region_id: Optional[str] = None) -> int:
        if region_id:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM tracked_properties WHERE region_id = ? AND is_new = 1",
                (region_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM tracked_properties WHERE is_new = 1"
            )
        return cur.fetchone()[0]

    # ── monitor runs ──

    def start_run(self, region_id: str) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        self._conn.execute(
            """
            INSERT INTO monitor_runs (run_id, region_id, started_at, status)
            VALUES (?, ?, ?, 'running')
            """,
            (run_id, region_id, now),
        )
        self._conn.commit()
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str = "completed",
        stats: Optional[dict] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        self._conn.execute(
            """
            UPDATE monitor_runs
            SET finished_at = ?, status = ?, stats_json = ?
            WHERE run_id = ?
            """,
            (now, status, json.dumps(stats or {}), run_id),
        )
        self._conn.commit()

    def get_runs(
        self, region_id: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        if region_id:
            cur = self._conn.execute(
                """
                SELECT * FROM monitor_runs
                WHERE region_id = ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (region_id, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM monitor_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in cur.fetchall()]

    # ── utilities ──

    def summary(self) -> dict:
        """Get a high-level summary of the monitoring database."""
        regions = self._conn.execute(
            "SELECT COUNT(*) FROM monitored_regions"
        ).fetchone()[0]
        props = self._conn.execute(
            "SELECT COUNT(*) FROM tracked_properties"
        ).fetchone()[0]
        new_props = self._conn.execute(
            "SELECT COUNT(*) FROM tracked_properties WHERE is_new = 1"
        ).fetchone()[0]
        snapshots = self._conn.execute(
            "SELECT COUNT(*) FROM analysis_snapshots"
        ).fetchone()[0]
        runs = self._conn.execute(
            "SELECT COUNT(*) FROM monitor_runs"
        ).fetchone()[0]
        return {
            "regions": regions,
            "tracked_properties": props,
            "new_properties": new_props,
            "analysis_snapshots": snapshots,
            "monitor_runs": runs,
        }
