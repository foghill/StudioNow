from __future__ import annotations

import importlib
import json
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
from .normalize import normalize_listings, save_raw, save_results

logger = logging.getLogger(__name__)

# ── Scheduler config ──────────────────────────────────────────────────────────

# Set SCRAPE_INTERVAL_HOURS to control how often the server auto-scrapes.
# Set to 0 to disable automatic scraping (manual-only mode).
SCRAPE_INTERVAL_HOURS: float = float(os.getenv("SCRAPE_INTERVAL_HOURS", "24"))

# ── In-memory cache ──────────────────────────────────────────────────────────

_cache: dict = {"listings": [], "generated_at": None, "total": 0}

_scrape_status: dict = {
    "running": False,
    "last_run": None,
    "last_source": None,
    "listings_added": 0,
    "error": None,
}

_scrape_lock = threading.Lock()

# APScheduler instance — set during lifespan startup
_scheduler = None


def _listings_path() -> str:
    config = Config()
    return os.path.join(config.data_dir, "normalized", "listings.json")


def _load_cache() -> None:
    """Load (or reload) the in-memory listing cache from listings.json."""
    path = _listings_path()
    if not os.path.exists(path):
        logger.warning("listings.json not found — cache empty. Run POST /scrape to populate.")
        return
    with open(path) as f:
        data = json.load(f)
    _cache["listings"] = data.get("listings", [])
    _cache["generated_at"] = data.get("generated_at")
    _cache["total"] = len(_cache["listings"])
    logger.info("Cache loaded: %d listings (generated %s)", _cache["total"], _cache["generated_at"])


def _cache_age_hours() -> float | None:
    """Return how many hours ago the cache was generated, or None if unknown."""
    generated_at = _cache.get("generated_at")
    if not generated_at:
        return None
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


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
    }
    path = registry.get(name)
    if not path:
        raise ValueError(f"Unknown source: {name}")
    module_path, class_name = path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _run_scrape(source: str | None, priority: str | None, include_restricted: bool) -> None:
    """Executed in a daemon thread — scrapes, normalizes, and refreshes the cache."""
    with _scrape_lock:
        if _scrape_status["running"]:
            return
        _scrape_status["running"] = True
        _scrape_status["error"] = None
        _scrape_status["last_source"] = source or priority or "high-priority"

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

        all_listings = []
        for name in names:
            try:
                cls = _import_scraper(name)
                scraper = cls(client=client, config=config)
                result = scraper.run()
                save_raw(name, [l.model_dump(mode="json") for l in result.listings], config)
                all_listings.extend(result.listings)
                logger.info("%s: %d listings, %d credits", name, len(result.listings), result.credits_used)
            except CreditExhaustedError as e:
                logger.warning("Credit limit hit, stopping: %s", e)
                break
            except Exception as e:
                logger.error("%s failed: %s", name, e)

        normalized, rejected = normalize_listings(all_listings)
        save_results(normalized, rejected, config)
        _load_cache()

        _scrape_status["last_run"] = datetime.now(timezone.utc).isoformat()
        _scrape_status["listings_added"] = len(normalized)
        logger.info("Scrape complete: %d listings saved", len(normalized))

    except Exception as e:
        _scrape_status["error"] = str(e)
        logger.exception("Scrape failed")
    finally:
        _scrape_status["running"] = False


def _trigger_scheduled_scrape() -> None:
    """Called by APScheduler — runs high-priority sources in a daemon thread."""
    logger.info("Scheduled scrape triggered")
    thread = threading.Thread(
        target=_run_scrape,
        args=(None, None, False),
        daemon=True,
    )
    thread.start()


def _first_run_delay() -> datetime | None:
    """
    Return when the first scheduled scrape should fire.
    If the cache is fresh (age < interval), delay the first run so we don't
    scrape immediately on every server restart.
    Returns None to fire immediately.
    """
    if SCRAPE_INTERVAL_HOURS <= 0:
        return None
    age = _cache_age_hours()
    if age is None:
        # No cache at all — scrape soon (1 minute delay to let server finish starting)
        return datetime.now(timezone.utc) + timedelta(minutes=1)
    remaining = SCRAPE_INTERVAL_HOURS - age
    if remaining <= 0:
        # Cache is stale — scrape soon
        return datetime.now(timezone.utc) + timedelta(minutes=1)
    # Cache is fresh — delay first run until the interval has elapsed
    return datetime.now(timezone.utc) + timedelta(hours=remaining)


# ── Filtering ─────────────────────────────────────────────────────────────────

def _apply_filters(
    listings: list[dict],
    q: str | None,
    neighborhood: str | None,
    borough: str | None,
    min_price: float | None,
    max_price: float | None,
    min_sqft: int | None,
    max_sqft: int | None,
    source: str | None,
    shared_ok: bool | None,
) -> list[dict]:
    results = listings

    if q:
        ql = q.lower()
        results = [
            l for l in results
            if ql in (l.get("title") or "").lower()
            or ql in (l.get("address") or "").lower()
            or ql in (l.get("neighborhood") or "").lower()
            or ql in (l.get("description") or "").lower()
        ]

    if neighborhood:
        nl = neighborhood.lower()
        results = [l for l in results if nl in (l.get("neighborhood") or "").lower()]

    if borough:
        bl = borough.lower()
        results = [l for l in results if (l.get("borough") or "").lower() == bl]

    if min_price is not None:
        results = [l for l in results if (l.get("price_monthly") or 0) >= min_price]

    if max_price is not None:
        results = [l for l in results if l.get("price_monthly") is not None and l["price_monthly"] <= max_price]

    if min_sqft is not None:
        results = [l for l in results if (l.get("size_sqft") or 0) >= min_sqft]

    if max_sqft is not None:
        results = [l for l in results if l.get("size_sqft") is not None and l["size_sqft"] <= max_sqft]

    if source:
        results = [l for l in results if l.get("source") == source]

    if shared_ok is not None:
        results = [
            l for l in results
            if l.get("lease_terms") is not None
            and l["lease_terms"].get("shared_ok") == shared_ok
        ]

    return results


# ── Request / response schemas ────────────────────────────────────────────────

class ListingsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    cached_at: str | None
    listings: list[dict]


class ScrapeRequest(BaseModel):
    source: str | None = None        # e.g. "rockella"
    priority: str | None = None      # "high" | "medium" | "low"
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
    global _scheduler
    _load_cache()

    if SCRAPE_INTERVAL_HOURS > 0:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            _scheduler = BackgroundScheduler()
            first_run = _first_run_delay()
            _scheduler.add_job(
                _trigger_scheduled_scrape,
                "interval",
                hours=SCRAPE_INTERVAL_HOURS,
                next_run_time=first_run,
                id="scheduled_scrape",
            )
            _scheduler.start()
            logger.info(
                "Scheduler started — interval: %gh, first run: %s",
                SCRAPE_INTERVAL_HOURS,
                first_run.isoformat() if first_run else "now",
            )
        except ImportError:
            logger.warning("apscheduler not installed — auto-scraping disabled. Run: pip install apscheduler")
    else:
        logger.info("Auto-scraping disabled (SCRAPE_INTERVAL_HOURS=0)")

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(
    title="Studio Now API",
    description=(
        "Local listings API for the Studio Now iOS app. "
        "Scrapes NYC artist studio spaces via Firecrawl and caches them for fast querying."
    ),
    version="1.1.0",
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


@app.get("/health", summary="Cache status, listing count, and next scheduled scrape")
async def health():
    next_run = None
    if _scheduler is not None:
        job = _scheduler.get_job("scheduled_scrape")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    age = _cache_age_hours()
    return {
        "status": "ok",
        "listings_cached": _cache["total"],
        "cached_at": _cache["generated_at"],
        "cache_age_hours": (int(float(age) * 100) / 100) if age is not None else None,
        "scrape_running": _scrape_status["running"],
        "scrape_interval_hours": SCRAPE_INTERVAL_HOURS if SCRAPE_INTERVAL_HOURS > 0 else None,
        "next_scheduled_scrape": next_run,
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
    source: Annotated[str | None, Query(description="Filter by source: rockella | chashama | spacefinder | etc.")] = None,
    shared_ok: Annotated[bool | None, Query(description="Filter by co-tenant availability")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Results per page (max 200)")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
):
    filtered = _apply_filters(
        _cache["listings"],
        q=q,
        neighborhood=neighborhood,
        borough=borough,
        min_price=min_price,
        max_price=max_price,
        min_sqft=min_sqft,
        max_sqft=max_sqft,
        source=source,
        shared_ok=shared_ok,
    )
    return ListingsResponse(
        total=len(filtered),
        offset=offset,
        limit=limit,
        cached_at=_cache["generated_at"],
        listings=filtered[offset: offset + limit],
    )


@app.get("/listings/{listing_id}", summary="Get a single listing by ID")
async def get_listing(listing_id: str):
    for listing in _cache["listings"]:
        if listing.get("id") == listing_id:
            return listing
    raise HTTPException(status_code=404, detail=f"Listing '{listing_id}' not found")


@app.get("/sources", summary="List all available scraper sources")
async def get_sources():
    return {
        "sources": [
            {
                "name": s.name,
                "priority": s.priority,
                "restricted": s.restricted,
                "enabled": s.enabled,
            }
            for s in SOURCES
        ]
    }


@app.post("/scrape", status_code=202, summary="Trigger a background scrape")
async def trigger_scrape(body: ScrapeRequest = ScrapeRequest()):
    """
    Starts a background scrape and returns immediately (HTTP 202).
    Poll `GET /scrape/status` to track progress.

    - No body → runs all high-priority sources (rockella, chashama, spacefinder)
    - `{"source": "rockella"}` → single source
    - `{"priority": "medium"}` → all medium-priority sources
    - `{"include_restricted": true}` → include Craigslist and StreetEasy
    """
    if _scrape_status["running"]:
        raise HTTPException(status_code=409, detail="A scrape is already running. Poll /scrape/status.")

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


@app.post("/cache/reload", summary="Reload the in-memory cache from listings.json")
async def reload_cache():
    """Force a cache reload without re-scraping — useful if you ran the scraper manually."""
    _load_cache()
    return {"listings_cached": _cache["total"], "cached_at": _cache["generated_at"]}
