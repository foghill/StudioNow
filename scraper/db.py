"""
SQLite database layer for Studio Now listings.

Provides:
- Schema with indexes for all filter dimensions (borough, neighborhood, price, sqft, source)
- FTS5 full-text search across title, address, neighborhood, description, amenities
- R-tree spatial index for geo queries (nearby studios)
- Upsert logic with last_seen_at tracking for stale detection
- Scrape run audit trail
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import Config
from .models import StudioListing

logger = logging.getLogger(__name__)

# How many days before a listing not seen in a scrape is marked stale
STALE_AFTER_DAYS = 7


def _db_path(config: Config | None = None) -> str:
    config = config or Config()
    return os.path.join(config.data_dir, "listings.db")


def get_connection(db_path: str | None = None, config: Config | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and row factory."""
    path = db_path or _db_path(config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Main listings table
CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    source_id       TEXT,
    title           TEXT NOT NULL,
    address         TEXT,
    neighborhood    TEXT,
    borough         TEXT,
    latitude        REAL,
    longitude       REAL,
    size_sqft       INTEGER,
    price_monthly   REAL,
    photos          TEXT,           -- JSON array
    amenities       TEXT,           -- JSON array
    description     TEXT,
    lease_terms     TEXT,           -- JSON object
    use_type        TEXT,
    scraped_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    stale           INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Indexes for every filter dimension
CREATE INDEX IF NOT EXISTS idx_listings_borough      ON listings(borough);
CREATE INDEX IF NOT EXISTS idx_listings_neighborhood ON listings(neighborhood);
CREATE INDEX IF NOT EXISTS idx_listings_price        ON listings(price_monthly);
CREATE INDEX IF NOT EXISTS idx_listings_size         ON listings(size_sqft);
CREATE INDEX IF NOT EXISTS idx_listings_source       ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_stale        ON listings(stale);
CREATE INDEX IF NOT EXISTS idx_listings_use_type     ON listings(use_type);

-- Composite index for the most common query pattern
CREATE INDEX IF NOT EXISTS idx_listings_borough_price ON listings(borough, price_monthly);
CREATE INDEX IF NOT EXISTS idx_listings_borough_size  ON listings(borough, size_sqft);

-- Scrape run audit trail
CREATE TABLE IF NOT EXISTS scrape_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    sources         TEXT,           -- JSON array of source names
    listings_added  INTEGER DEFAULT 0,
    listings_updated INTEGER DEFAULT 0,
    listings_staled INTEGER DEFAULT 0,
    credits_used    INTEGER DEFAULT 0,
    errors          TEXT,           -- JSON array
    status          TEXT NOT NULL DEFAULT 'running'  -- running, completed, failed
);
"""

FTS_SQL = """
-- Full-text search index (standalone, rebuilt after upserts)
CREATE VIRTUAL TABLE IF NOT EXISTS listings_fts USING fts5(
    listing_id,
    title,
    address,
    neighborhood,
    description,
    amenities,
    tokenize='porter unicode61'
);
"""

RTREE_SQL = """
-- R-tree spatial index for geo queries
CREATE VIRTUAL TABLE IF NOT EXISTS listings_geo USING rtree(
    rowid_ref,
    min_lat, max_lat,
    min_lng, max_lng
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, FTS, and R-tree if they don't exist."""
    conn.executescript(SCHEMA_SQL)
    # FTS and R-tree need separate handling since executescript can't mix virtual tables
    for stmt in FTS_SQL.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Trigger/table already exists
    for stmt in RTREE_SQL.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    logger.info("Database initialized at %s", conn.execute("PRAGMA database_list").fetchone()[2])


# ── Write operations ──────────────────────────────────────────────────────────

def upsert_listing(conn: sqlite3.Connection, listing: StudioListing) -> str:
    """
    Insert or update a listing. Returns 'inserted' or 'updated'.

    On conflict (same id): updates all fields and refreshes last_seen_at.
    """
    now = datetime.now(timezone.utc).isoformat()
    photos_json = json.dumps(listing.photos) if listing.photos else "[]"
    amenities_json = json.dumps(listing.amenities) if listing.amenities else "[]"
    lease_json = json.dumps(listing.lease_terms.model_dump()) if listing.lease_terms else None
    borough_val = listing.borough.value if listing.borough else None

    # Check if exists
    existing = conn.execute("SELECT id FROM listings WHERE id = ?", (listing.id,)).fetchone()

    if existing:
        conn.execute("""
            UPDATE listings SET
                source=?, source_url=?, source_id=?, title=?, address=?,
                neighborhood=?, borough=?, latitude=?, longitude=?,
                size_sqft=?, price_monthly=?, photos=?, amenities=?,
                description=?, lease_terms=?, use_type=?, scraped_at=?,
                last_seen_at=?, stale=0, updated_at=?
            WHERE id=?
        """, (
            listing.source, listing.source_url, listing.source_id, listing.title,
            listing.address, listing.neighborhood, borough_val,
            listing.latitude, listing.longitude, listing.size_sqft,
            listing.price_monthly, photos_json, amenities_json,
            listing.description, lease_json, listing.use_type,
            listing.scraped_at, now, now, listing.id,
        ))
        return "updated"
    else:
        conn.execute("""
            INSERT INTO listings (
                id, source, source_url, source_id, title, address,
                neighborhood, borough, latitude, longitude,
                size_sqft, price_monthly, photos, amenities,
                description, lease_terms, use_type, scraped_at,
                last_seen_at, stale, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (
            listing.id, listing.source, listing.source_url, listing.source_id,
            listing.title, listing.address, listing.neighborhood, borough_val,
            listing.latitude, listing.longitude, listing.size_sqft,
            listing.price_monthly, photos_json, amenities_json,
            listing.description, lease_json, listing.use_type,
            listing.scraped_at, now, now, now,
        ))
        # Insert into R-tree if we have coordinates
        if listing.latitude and listing.longitude:
            rowid = conn.execute("SELECT rowid FROM listings WHERE id=?", (listing.id,)).fetchone()[0]
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO listings_geo VALUES (?, ?, ?, ?, ?)",
                    (rowid, listing.latitude, listing.latitude, listing.longitude, listing.longitude),
                )
            except sqlite3.OperationalError:
                pass  # R-tree might not exist in test DBs
        return "inserted"


def upsert_listings(conn: sqlite3.Connection, listings: list[StudioListing]) -> dict:
    """Bulk upsert. Returns counts: {'inserted': N, 'updated': M}."""
    counts = {"inserted": 0, "updated": 0}
    for listing in listings:
        result = upsert_listing(conn, listing)
        counts[result] += 1
    conn.commit()

    # Rebuild search and geo indexes
    _rebuild_fts_index(conn)
    _rebuild_geo_index(conn)

    logger.info("Upsert complete: %d inserted, %d updated", counts["inserted"], counts["updated"])
    return counts


def mark_stale(conn: sqlite3.Connection, source: str, seen_ids: set[str]) -> int:
    """
    Mark listings from a source as stale if they weren't in the latest scrape.
    Only marks listings stale if they haven't been seen for STALE_AFTER_DAYS.
    Returns number of listings marked stale.
    """
    if not seen_ids:
        return 0

    placeholders = ",".join("?" for _ in seen_ids)
    cutoff = datetime.now(timezone.utc).isoformat()

    # Get listings from this source that were NOT in the current scrape
    cursor = conn.execute(f"""
        UPDATE listings
        SET stale = 1, updated_at = ?
        WHERE source = ?
          AND id NOT IN ({placeholders})
          AND stale = 0
          AND julianday(?) - julianday(last_seen_at) > ?
    """, (cutoff, source, *seen_ids, cutoff, STALE_AFTER_DAYS))

    count = cursor.rowcount
    conn.commit()
    if count:
        logger.info("Marked %d listings from %s as stale", count, source)
    return count


def _rebuild_fts_index(conn: sqlite3.Connection) -> None:
    """Rebuild the FTS5 index from current listings data."""
    try:
        conn.execute("DELETE FROM listings_fts")
        conn.execute("""
            INSERT INTO listings_fts (listing_id, title, address, neighborhood, description, amenities)
            SELECT id, title, COALESCE(address, ''), COALESCE(neighborhood, ''),
                   COALESCE(description, ''), COALESCE(amenities, '')
            FROM listings
            WHERE stale = 0
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # FTS table might not exist


def _rebuild_geo_index(conn: sqlite3.Connection) -> None:
    """Rebuild the R-tree index from listings with coordinates."""
    try:
        conn.execute("DELETE FROM listings_geo")
        conn.execute("""
            INSERT INTO listings_geo (rowid_ref, min_lat, max_lat, min_lng, max_lng)
            SELECT rowid, latitude, latitude, longitude, longitude
            FROM listings
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND stale = 0
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # R-tree table might not exist


# ── Read operations ───────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a dict, parsing JSON fields."""
    d = dict(row)
    # Parse JSON fields
    for field in ("photos", "amenities"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    if d.get("lease_terms") and isinstance(d["lease_terms"], str):
        try:
            d["lease_terms"] = json.loads(d["lease_terms"])
        except (json.JSONDecodeError, TypeError):
            d["lease_terms"] = None
    # Convert stale int to bool
    d["stale"] = bool(d.get("stale", 0))
    return d


def query_listings(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    neighborhood: str | None = None,
    borough: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_sqft: int | None = None,
    max_sqft: int | None = None,
    source: str | None = None,
    shared_ok: bool | None = None,
    include_stale: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Query listings with filters. Returns (results, total_count).

    Uses FTS5 for full-text search (q parameter).
    All other filters use indexed SQL WHERE clauses.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if not include_stale:
        conditions.append("l.stale = 0")

    if q:
        # Use FTS5 for full-text search
        conditions.append("l.id IN (SELECT listing_id FROM listings_fts WHERE listings_fts MATCH ?)")
        # Escape special FTS characters and add * for prefix matching
        fts_query = q.replace('"', '""')
        params.append(f'"{fts_query}"')

    if neighborhood:
        conditions.append("LOWER(l.neighborhood) LIKE ?")
        params.append(f"%{neighborhood.lower()}%")

    if borough:
        conditions.append("LOWER(l.borough) = ?")
        params.append(borough.lower())

    if min_price is not None:
        conditions.append("l.price_monthly >= ?")
        params.append(min_price)

    if max_price is not None:
        conditions.append("l.price_monthly IS NOT NULL AND l.price_monthly <= ?")
        params.append(max_price)

    if min_sqft is not None:
        conditions.append("l.size_sqft >= ?")
        params.append(min_sqft)

    if max_sqft is not None:
        conditions.append("l.size_sqft IS NOT NULL AND l.size_sqft <= ?")
        params.append(max_sqft)

    if source:
        conditions.append("l.source = ?")
        params.append(source)

    if shared_ok is not None:
        conditions.append("json_extract(l.lease_terms, '$.shared_ok') = ?")
        params.append(1 if shared_ok else 0)

    where = " AND ".join(conditions) if conditions else "1=1"

    # Count query
    count_sql = f"SELECT COUNT(*) FROM listings l WHERE {where}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Results query with pagination
    # Prioritize listings with real data (price + sqft) at the top
    results_sql = f"""
        SELECT l.* FROM listings l
        WHERE {where}
        ORDER BY
            CASE WHEN l.price_monthly IS NOT NULL AND l.price_monthly > 0 THEN 0 ELSE 1 END,
            CASE WHEN l.size_sqft IS NOT NULL AND l.size_sqft > 0 THEN 0 ELSE 1 END,
            l.price_monthly ASC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(results_sql, params + [limit, offset]).fetchall()

    return [_row_to_dict(row) for row in rows], total


def get_listing_by_id(conn: sqlite3.Connection, listing_id: str) -> dict | None:
    """Get a single listing by ID."""
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return _row_to_dict(row) if row else None


def query_nearby(
    conn: sqlite3.Connection,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    limit: int = 50,
) -> list[dict]:
    """
    Find listings near a point using R-tree index.

    Approximation: 1 degree latitude ≈ 111 km, 1 degree longitude ≈ 85 km at NYC latitude.
    """
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / 85.0

    rows = conn.execute("""
        SELECT l.* FROM listings l
        INNER JOIN listings_geo g ON g.rowid_ref = l.rowid
        WHERE g.min_lat >= ? AND g.max_lat <= ?
          AND g.min_lng >= ? AND g.max_lng <= ?
          AND l.stale = 0
        ORDER BY ABS(l.latitude - ?) + ABS(l.longitude - ?)
        LIMIT ?
    """, (
        lat - lat_delta, lat + lat_delta,
        lng - lng_delta, lng + lng_delta,
        lat, lng,
        limit,
    )).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get database statistics."""
    total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM listings WHERE stale = 0").fetchone()[0]
    stale = conn.execute("SELECT COUNT(*) FROM listings WHERE stale = 1").fetchone()[0]
    with_coords = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    ).fetchone()[0]

    sources = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM listings WHERE stale = 0 GROUP BY source"):
        sources[row["source"]] = row["cnt"]

    boroughs = {}
    for row in conn.execute(
        "SELECT borough, COUNT(*) as cnt FROM listings WHERE stale = 0 AND borough IS NOT NULL GROUP BY borough"
    ):
        boroughs[row["borough"]] = row["cnt"]

    last_run = conn.execute(
        "SELECT finished_at FROM scrape_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    return {
        "total_listings": total,
        "active_listings": active,
        "stale_listings": stale,
        "with_coordinates": with_coords,
        "by_source": sources,
        "by_borough": boroughs,
        "last_scrape": last_run["finished_at"] if last_run else None,
    }


# ── Scrape run tracking ──────────────────────────────────────────────────────

def start_scrape_run(conn: sqlite3.Connection, sources: list[str]) -> int:
    """Record the start of a scrape run. Returns the run ID."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO scrape_runs (started_at, sources, status) VALUES (?, ?, 'running')",
        (now, json.dumps(sources)),
    )
    conn.commit()
    return cursor.lastrowid


def finish_scrape_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    listings_added: int = 0,
    listings_updated: int = 0,
    listings_staled: int = 0,
    credits_used: int = 0,
    errors: list[str] | None = None,
    status: str = "completed",
) -> None:
    """Record the completion of a scrape run."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE scrape_runs SET
            finished_at=?, listings_added=?, listings_updated=?, listings_staled=?,
            credits_used=?, errors=?, status=?
        WHERE id=?
    """, (
        now, listings_added, listings_updated, listings_staled,
        credits_used, json.dumps(errors or []), status, run_id,
    ))
    conn.commit()


# ── Migration ─────────────────────────────────────────────────────────────────

def import_from_json(conn: sqlite3.Connection, json_path: str) -> dict:
    """
    Import listings from an existing listings.json file into SQLite.
    Returns counts: {'inserted': N, 'updated': M, 'skipped': K}.
    """
    with open(json_path) as f:
        data = json.load(f)

    raw_listings = data.get("listings", [])
    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    for raw in raw_listings:
        try:
            # Parse photos/amenities if they're already lists
            listing = StudioListing(**raw)
            result = upsert_listing(conn, listing)
            counts[result] += 1
        except Exception as e:
            logger.warning("Skipping invalid listing: %s", e)
            counts["skipped"] += 1

    conn.commit()
    _rebuild_fts_index(conn)
    _rebuild_geo_index(conn)

    logger.info(
        "JSON import: %d inserted, %d updated, %d skipped",
        counts["inserted"], counts["updated"], counts["skipped"],
    )
    return counts
