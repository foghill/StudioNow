from __future__ import annotations

import importlib
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .config import Config, SOURCES
from .db import (
    finish_scrape_run,
    get_connection,
    get_listing_by_id,
    get_stats,
    init_db,
    mark_stale,
    query_listings,
    query_nearby,
    start_scrape_run,
    upsert_listings,
)
from .normalize import normalize_listings, save_raw

logger = logging.getLogger(__name__)

# ── Scheduler config ──────────────────────────────────────────────────────────

# Schedule: cron-based (6 AM and 6 PM ET) or interval-based fallback.
# Set SCRAPE_CRON=1 (default) to use 6am/6pm ET schedule.
# Set SCRAPE_INTERVAL_HOURS to a number > 0 to use fixed interval instead.
# Set both to 0 / empty to disable auto-scraping.
SCRAPE_CRON: bool = os.getenv("SCRAPE_CRON", "1") == "1"
SCRAPE_INTERVAL_HOURS: float = float(os.getenv("SCRAPE_INTERVAL_HOURS", "0"))

# ── Shared state ──────────────────────────────────────────────────────────────

_db_conn = None  # Set during lifespan startup

_scrape_status: dict = {
    "running": False,
    "last_run": None,
    "last_source": None,
    "listings_added": 0,
    "error": None,
}

_scrape_lock = threading.Lock()
_scheduler = None


def _get_db():
    """Get the shared database connection."""
    global _db_conn
    if _db_conn is None:
        config = Config()
        _db_conn = get_connection(config=config)
        init_db(_db_conn)
    return _db_conn


# ── Background scrape ────────────────────────────────────────────────────────

def _import_scraper(name: str):
    registry = {
        "rockella":        "scraper.sources.rockella:RockellaScraper",
        "chashama":        "scraper.sources.chashama:ChashamaScraper",
        "spacefinder":     "scraper.sources.spacefinder:SpacefinderScraper",
        "loopnet":         "scraper.sources.loopnet:LoopnetScraper",
        "nyfa":            "scraper.sources.nyfa:NyfaScraper",
        "listings_project":"scraper.sources.listings_project:ListingsProjectScraper",
        "craigslist":      "scraper.sources.craigslist:CraigslistScraper",
        "streeteasy":      "scraper.sources.streeteasy:StreeteasyScraper",
        "nyc_opendata":    "scraper.sources.nyc_opendata:NycOpendataScraper",
        "coworker":        "scraper.sources.coworker:CoworkerScraper",
        "ny_studio_factory":"scraper.sources.ny_studio_factory:NyStudioFactoryScraper",
        "navy_yard":       "scraper.sources.navy_yard:NavyYardScraper",
        "gmdc":            "scraper.sources.gmdc:GmdcScraper",
        "mana_contemporary":"scraper.sources.mana_contemporary:ManaContemporaryScraper",
        "pioneer_works":   "scraper.sources.pioneer_works:PioneerWorksScraper",
        "industry_city":   "scraper.sources.industry_city:IndustryCityScraper",
    }
    path = registry.get(name)
    if not path:
        raise ValueError(f"Unknown source: {name}")
    module_path, class_name = path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _run_scrape(source: str | None, priority: str | None, include_restricted: bool) -> None:
    """Executed in a daemon thread — scrapes, normalizes, and writes to SQLite."""
    with _scrape_lock:
        if _scrape_status["running"]:
            return
        _scrape_status["running"] = True
        _scrape_status["error"] = None
        _scrape_status["last_source"] = source or priority or "high-priority"

    conn = _get_db()
    total_inserted = 0
    total_updated = 0
    total_staled = 0
    total_credits = 0
    all_errors: list[str] = []
    run_id = None

    try:
        from .client import CreditExhaustedError, FirecrawlClient

        config = Config()
        config.validate()
        client = FirecrawlClient(config)

        if source:
            names = [source]
        elif priority:
            names = [s.name for s in config.get_sources(priority=priority, include_restricted=include_restricted)]
        else:
            names = [s.name for s in config.get_sources(priority="high")]

        run_id = start_scrape_run(conn, names)

        for name in names:
            try:
                cls = _import_scraper(name)
                scraper = cls(client=client, config=config)
                result = scraper.run()
                save_raw(name, [l.model_dump(mode="json") for l in result.listings], config)

                # Normalize
                normalized, _ = normalize_listings(result.listings)

                # Upsert into SQLite
                counts = upsert_listings(conn, normalized)
                total_inserted += counts["inserted"]
                total_updated += counts["updated"]

                # Mark stale listings from this source
                seen_ids = {l.id for l in normalized if l.id}
                staled = mark_stale(conn, name, seen_ids)
                total_staled += staled

                total_credits += result.credits_used
                all_errors.extend(result.errors)

                logger.info(
                    "%s: %d listings (%d new, %d updated, %d staled), %d credits",
                    name, len(normalized), counts["inserted"], counts["updated"],
                    staled, result.credits_used,
                )
            except CreditExhaustedError as e:
                logger.warning("Credit limit hit, stopping: %s", e)
                all_errors.append(f"Credit exhausted: {e}")
                break
            except Exception as e:
                logger.error("%s failed: %s", name, e)
                all_errors.append(f"{name}: {e}")

        _scrape_status["last_run"] = datetime.now(timezone.utc).isoformat()
        _scrape_status["listings_added"] = total_inserted + total_updated
        logger.info(
            "Scrape complete: %d inserted, %d updated, %d staled",
            total_inserted, total_updated, total_staled,
        )

        if run_id:
            finish_scrape_run(
                conn, run_id,
                listings_added=total_inserted,
                listings_updated=total_updated,
                listings_staled=total_staled,
                credits_used=total_credits,
                errors=all_errors,
                status="completed",
            )

    except Exception as e:
        _scrape_status["error"] = str(e)
        logger.exception("Scrape failed")
        if run_id:
            finish_scrape_run(conn, run_id, errors=[str(e)], status="failed")
    finally:
        _scrape_status["running"] = False


def _trigger_scheduled_scrape() -> None:
    logger.info("Scheduled scrape triggered")
    thread = threading.Thread(target=_run_scrape, args=(None, None, False), daemon=True)
    thread.start()


# ── Request / response schemas ────────────────────────────────────────────────

class ListingsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    listings: list[dict]


class ScrapeRequest(BaseModel):
    source: str | None = None
    priority: str | None = None
    include_restricted: bool = False


class ScrapeStatusResponse(BaseModel):
    running: bool
    last_run: str | None
    last_source: str | None
    listings_added: int
    error: str | None


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler, _db_conn

    # Initialize database
    config = Config()
    _db_conn = get_connection(config=config)
    init_db(_db_conn)

    stats = get_stats(_db_conn)
    logger.info("Database ready: %d active listings", stats["active_listings"])

    # If DB is empty, try importing from existing listings.json
    if stats["total_listings"] == 0:
        json_path = os.path.join(config.data_dir, "normalized", "listings.json")
        if os.path.exists(json_path):
            from .db import import_from_json
            counts = import_from_json(_db_conn, json_path)
            logger.info("Imported from listings.json: %s", counts)

    # Start scheduler
    if SCRAPE_CRON or SCRAPE_INTERVAL_HOURS > 0:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger

            _scheduler = BackgroundScheduler()

            if SCRAPE_CRON:
                # 6:00 AM ET and 6:00 PM ET, every day
                _scheduler.add_job(
                    _trigger_scheduled_scrape,
                    CronTrigger(hour=6, minute=0, timezone="US/Eastern"),
                    id="scrape_6am",
                )
                _scheduler.add_job(
                    _trigger_scheduled_scrape,
                    CronTrigger(hour=18, minute=0, timezone="US/Eastern"),
                    id="scrape_6pm",
                )
                _scheduler.start()
                logger.info("Scheduler started — cron: 6:00 AM and 6:00 PM ET daily")
            else:
                _scheduler.add_job(
                    _trigger_scheduled_scrape,
                    "interval",
                    hours=SCRAPE_INTERVAL_HOURS,
                    next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
                    id="scheduled_scrape",
                )
                _scheduler.start()
                logger.info("Scheduler started — interval: %gh", SCRAPE_INTERVAL_HOURS)
        except ImportError:
            logger.warning("apscheduler not installed — auto-scraping disabled.")
    else:
        logger.info("Auto-scraping disabled (SCRAPE_CRON=0, SCRAPE_INTERVAL_HOURS=0)")

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    if _db_conn is not None:
        _db_conn.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Studio Now API",
    description=(
        "Listings API for the Studio Now iOS app. "
        "Queries a SQLite database of NYC artist studio spaces "
        "collected from 16 sources via Firecrawl and public APIs."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


@app.get("/health", summary="Database stats and scheduler status")
async def health():
    conn = _get_db()
    stats = get_stats(conn)

    next_runs = []
    if _scheduler is not None:
        for job in _scheduler.get_jobs():
            if job.next_run_time:
                next_runs.append({"id": job.id, "next_run": job.next_run_time.isoformat()})
    next_runs.sort(key=lambda x: x["next_run"])

    schedule_mode = "cron (6am/6pm ET)" if SCRAPE_CRON else (
        f"interval ({SCRAPE_INTERVAL_HOURS}h)" if SCRAPE_INTERVAL_HOURS > 0 else "disabled"
    )

    return {
        "status": "ok",
        **stats,
        "scrape_running": _scrape_status["running"],
        "schedule": schedule_mode,
        "next_scheduled_scrapes": next_runs,
    }


@app.get("/listings", response_model=ListingsResponse, summary="Query listings with filters")
async def get_listings(
    q: Annotated[str | None, Query(description="Full-text search across title, address, neighborhood, description")] = None,
    neighborhood: Annotated[str | None, Query(description="Partial neighborhood name match (case-insensitive)")] = None,
    borough: Annotated[str | None, Query(description="Exact borough: brooklyn | manhattan | queens | bronx | staten_island")] = None,
    min_price: Annotated[float | None, Query(ge=0, description="Minimum monthly rent (USD)")] = None,
    max_price: Annotated[float | None, Query(ge=0, description="Maximum monthly rent (USD)")] = None,
    min_sqft: Annotated[int | None, Query(ge=0, description="Minimum square footage")] = None,
    max_sqft: Annotated[int | None, Query(ge=0, description="Maximum square footage")] = None,
    source: Annotated[str | None, Query(description="Filter by source: rockella | nyc_opendata | etc.")] = None,
    shared_ok: Annotated[bool | None, Query(description="Filter by co-tenant availability")] = None,
    include_stale: Annotated[bool, Query(description="Include stale listings (not seen in recent scrapes)")] = False,
    limit: Annotated[int, Query(ge=1, le=2000, description="Results per page (max 2000)")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
):
    conn = _get_db()
    listings, total = query_listings(
        conn,
        q=q,
        neighborhood=neighborhood,
        borough=borough,
        min_price=min_price,
        max_price=max_price,
        min_sqft=min_sqft,
        max_sqft=max_sqft,
        source=source,
        shared_ok=shared_ok,
        include_stale=include_stale,
        limit=limit,
        offset=offset,
    )
    return ListingsResponse(total=total, offset=offset, limit=limit, listings=listings)


@app.get("/listings/nearby", summary="Find studios near a location")
async def get_nearby(
    lat: Annotated[float, Query(description="Latitude")],
    lng: Annotated[float, Query(description="Longitude")],
    radius_km: Annotated[float, Query(ge=0.1, le=50, description="Search radius in km")] = 5.0,
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
):
    conn = _get_db()
    listings = query_nearby(conn, lat=lat, lng=lng, radius_km=radius_km, limit=limit)
    return {"total": len(listings), "listings": listings}


@app.get("/listings/{listing_id}", summary="Get a single listing by ID")
async def get_listing(listing_id: str):
    conn = _get_db()
    listing = get_listing_by_id(conn, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail=f"Listing '{listing_id}' not found")
    return listing


@app.get("/sources", summary="List all available scraper sources")
async def get_sources():
    return {
        "sources": [
            {"name": s.name, "priority": s.priority, "restricted": s.restricted, "enabled": s.enabled}
            for s in SOURCES
        ]
    }


@app.post("/scrape", status_code=202, summary="Trigger a background scrape")
async def trigger_scrape(body: ScrapeRequest = ScrapeRequest()):
    """
    Starts a background scrape and returns immediately (HTTP 202).
    Poll `GET /scrape/status` to track progress.
    """
    if _scrape_status["running"]:
        raise HTTPException(status_code=409, detail="A scrape is already running.")

    thread = threading.Thread(
        target=_run_scrape,
        args=(body.source, body.priority, body.include_restricted),
        daemon=True,
    )
    thread.start()

    label = body.source or (f"priority={body.priority}" if body.priority else "high-priority sources")
    return {"message": "Scrape started", "scraping": label}


@app.get("/scrape/status", response_model=ScrapeStatusResponse, summary="Check scraping status")
async def get_scrape_status():
    return ScrapeStatusResponse(**_scrape_status)


@app.post("/seed", status_code=200, summary="Seed database from uploaded listings JSON")
async def seed_listings(body: dict):
    """
    Accept a listings.json payload and import into the database.
    Body should be: {"listings": [...]}
    """
    from .db import import_from_json as _import_json  # noqa: avoid name clash
    import tempfile, json as _json

    raw_listings = body.get("listings", [])
    if not raw_listings:
        raise HTTPException(status_code=400, detail="No listings in payload")

    # Write to a temp file and use existing import logic
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        _json.dump({"listings": raw_listings}, f)
        tmp_path = f.name

    try:
        conn = _get_db()
        counts = _import_json(conn, tmp_path)
        return {"message": "Seed complete", **counts}
    finally:
        os.unlink(tmp_path)


@app.get("/stats", summary="Detailed database statistics")
async def stats():
    conn = _get_db()
    return get_stats(conn)
