# Studio Now

An iOS app by [WORTHLESSSTUDIOS](https://worthlessstudios.org) that matches NYC artists with affordable studio spaces.

---

## Project Structure

```
StudioNow/
├── scraper/                  # Python data pipeline — scrapes studio listings
│   ├── sources/              # Per-site scraper implementations
│   ├── data/
│   │   ├── raw/              # Raw scraped output (per-source JSON)
│   │   └── normalized/       # Cleaned, deduplicated listings.json
│   ├── cli.py                # Command-line interface
│   ├── client.py             # Firecrawl API client
│   ├── config.py             # Source registry and configuration
│   ├── models.py             # Pydantic data models
│   ├── normalize.py          # Normalization and deduplication logic
│   ├── server.py             # FastAPI listings API with caching
│   └── generate_mockdata.py  # Converts listings.json → MockData.swift
├── StudioNow/
│   └── Data/
│       └── MockData.swift    # Auto-generated — do not edit by hand
├── scrape.sh                 # Run scrapers (bypasses system Python PATH issues)
├── serve.sh                  # Start the local API server
└── requirements.txt
```

---

## Scraper Setup

The scraper collects studio listings from multiple sources and outputs normalized JSON for use as mock data in the iOS app.

### Prerequisites

- Python 3.11+
- A [Firecrawl](https://firecrawl.dev) API key

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root:

```
FIRECRAWL_API_KEY=fc-your-key-here
```

---

## Scraper Usage

Run scrapers via `scrape.sh` (recommended — bypasses PATH issues with the system Python) or activate the venv manually first.

```bash
# Recommended
./scrape.sh run --source rockella

# Manual (equivalent)
.venv/bin/python -m scraper.cli run --source rockella
```

### Run high-priority sources (default)

```bash
source .venv/bin/activate
python -m scraper.cli run
```

### Run a specific source

```bash
python -m scraper.cli run --source rockella
python -m scraper.cli run --source chashama
python -m scraper.cli run --source spacefinder
```

### Run by priority level

```bash
python -m scraper.cli run --priority high
python -m scraper.cli run --priority medium
python -m scraper.cli run --priority low
```

### Run all sources

```bash
python -m scraper.cli run --all
```

### Include restricted sources

Craigslist and StreetEasy have Terms of Service restrictions and are excluded by default. Opt in explicitly:

```bash
python -m scraper.cli run --all --include-restricted
```

### Re-normalize without re-scraping

Re-run normalization over existing raw data:

```bash
python -m scraper.cli normalize
```

### List available sources

```bash
python -m scraper.cli sources
```

### Check raw data files

```bash
python -m scraper.cli credits
```

---

## Sources

| Source | Priority | Notes |
|---|---|---|
| rockella | high | |
| chashama | high | |
| spacefinder | high | |
| loopnet | medium | |
| nyfa | medium | |
| listings_project | medium | |
| craigslist | medium | Restricted — requires `--include-restricted` |
| streeteasy | low | Restricted — requires `--include-restricted` |

---

## Output

Normalized listings are written to `scraper/data/normalized/listings.json`.

---

## Updating the iOS App with New Listings

After scraping, run the generator to convert `listings.json` into `MockData.swift`:

```bash
.venv/bin/python scraper/generate_mockdata.py
```

Or using the convenience wrapper:

```bash
./scrape.sh run --source rockella   # scrape
.venv/bin/python scraper/generate_mockdata.py  # update the app
```

`MockData.swift` is fully auto-generated — **do not edit it by hand**. All changes to listings should come from re-running the scraper and generator.

The generator:
- Maps JSON fields to the Swift `StudioListing` model
- Falls back to neighborhood-based coordinates when lat/lon are missing
- Infers default amenities for known Rockella buildings
- Distributes `availableDate` values across the coming weeks

---

## Local API Server

A FastAPI server that serves cached listings from disk and auto-scrapes on a configurable schedule — so Firecrawl credits are only used on a timer, not on every request.

### Caching strategy

- On startup, the server loads `scraper/data/normalized/listings.json` into memory and serves all queries from that cache.
- A background scheduler (APScheduler) automatically runs the high-priority scrapers once every `SCRAPE_INTERVAL_HOURS` (default: 24). If the cache is already fresh when the server starts, it waits until the interval elapses before scraping again.
- The iOS app fetches from the server once per session and falls back to baked-in `MockData` when the server is unreachable.
- Use the refresh button (↻) or pull-to-refresh in the app to force a new fetch from the server.

### Start the server

```bash
./serve.sh
```

Runs at `http://127.0.0.1:8000`. Interactive docs (Swagger UI) at `http://127.0.0.1:8000/docs`.

Override host/port or scrape schedule:

```bash
HOST=0.0.0.0 PORT=9000 ./serve.sh

# Scrape every 12 hours instead of 24
SCRAPE_INTERVAL_HOURS=12 ./serve.sh

# Disable automatic scraping (manual-only)
SCRAPE_INTERVAL_HOURS=0 ./serve.sh
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Cache status, listing count, cache age, next scheduled scrape |
| `GET` | `/listings` | Query listings with filters (see below) |
| `GET` | `/listings/{id}` | Single listing by ID |
| `GET` | `/sources` | All available scraper sources |
| `POST` | `/scrape` | Trigger a manual background scrape (returns 202) |
| `GET` | `/scrape/status` | Poll scraping progress |
| `POST` | `/cache/reload` | Reload cache from listings.json without re-scraping |

### `GET /health` response

```json
{
  "status": "ok",
  "listings_cached": 33,
  "cached_at": "2026-03-25T03:00:00+00:00",
  "cache_age_hours": 2.5,
  "scrape_running": false,
  "scrape_interval_hours": 24,
  "next_scheduled_scrape": "2026-03-26T03:00:00+00:00"
}
```

`next_scheduled_scrape` is `null` when `SCRAPE_INTERVAL_HOURS=0`.

### Query parameters for `GET /listings`

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Full-text search across title, address, neighborhood, description |
| `neighborhood` | string | Partial match, case-insensitive (e.g. `brooklyn`) |
| `borough` | string | Exact match: `brooklyn`, `manhattan`, `queens`, `bronx`, `staten_island` |
| `min_price` | number | Minimum monthly rent (USD) |
| `max_price` | number | Maximum monthly rent (USD) |
| `min_sqft` | int | Minimum square footage |
| `max_sqft` | int | Maximum square footage |
| `source` | string | Filter by scraper: `rockella`, `chashama`, `spacefinder`, etc. |
| `shared_ok` | bool | Co-tenant availability (`true` / `false`) |
| `limit` | int | Results per page, max 200 (default 50) |
| `offset` | int | Pagination offset (default 0) |

**Examples:**

```bash
# All Brooklyn studios under $1,200/mo
curl "http://localhost:8000/listings?borough=brooklyn&max_price=1200"

# Search by address
curl "http://localhost:8000/listings?q=1639+Centre+St"

# Compact studios, sorted by cheapest (client-side sort)
curl "http://localhost:8000/listings?max_sqft=200&min_price=500"
```

### Trigger a manual scrape via API

```bash
# High-priority sources (default)
curl -X POST http://localhost:8000/scrape

# Single source
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"source": "rockella"}'

# All medium-priority sources
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"priority": "medium"}'

# Poll status
curl http://localhost:8000/scrape/status
```

---

## iOS App

Built with SwiftUI, targeting iOS 17+. Key screens:

1. **Onboarding** — Artist profile creation (name, discipline, portfolio link)
2. **Studio Needs Form** — Square footage, neighborhood, budget, lease dates, co-tenant preference
3. **Match Results** — List/map view with matching spaces and co-tenant compatibility scores
4. **Space Detail** — Full listing with photos, floor plan, amenities, and a request button
5. **Dashboard** — Application status, upcoming mediations, rent payment schedule, support resources
6. **Mediation & Support** — In-app messaging, scheduling, and a resource hub

Uses MapKit for neighborhood browsing and local mock JSON for prototype data.
