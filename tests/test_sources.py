"""
Source reachability and data retrieval tests.

Two test groups:
  reachability  — plain HTTP checks, no API key needed, no credits spent
  live          — runs real scrapers via Firecrawl, requires FIRECRAWL_API_KEY

Usage:
    # Reachability only (fast)
    pytest tests/test_sources.py -m reachability -v

    # Data retrieval (uses Firecrawl credits)
    pytest tests/test_sources.py -m live -v

    # Both
    pytest tests/test_sources.py -v

    # Standalone report (reachability only)
    python tests/test_sources.py
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from dataclasses import dataclass

import httpx
import pytest

# Make sure the project root is on the path so scraper imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# Source registry
# Each entry: (name, primary_url, restricted)
# ---------------------------------------------------------------------------
SOURCES = [
    ("rockella",         "https://rockella.space/",                                             False),
    ("chashama",         "https://chashama.org/programs/space-to-create/",                     False),
    ("spacefinder",      "https://nyc.spacefinder.org/spaces",                                 False),
    ("loopnet",          "https://www.loopnet.com/search/listings/live-work-space/ny/for-lease/", False),
    ("nyfa",             "https://www.nyfa.org/spaces/",                                        False),
    ("listings_project", "https://www.listingsproject.com",                                    False),
    ("craigslist",       "https://newyork.craigslist.org/search/off",                          True),
    ("streeteasy",       "https://streeteasy.com/for-rent/nyc/",                               True),
]

SOURCE_NAMES     = [s[0] for s in SOURCES]
SOURCE_IDS       = [s[0] for s in SOURCES]  # pytest parametrize IDs
RESTRICTED_NAMES = {s[0] for s in SOURCES if s[2]}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REACHABILITY_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scraper_class(name: str):
    """Dynamically load the scraper class for a given source name."""
    mod = importlib.import_module(f"scraper.sources.{name}")
    class_name = {
        "rockella":         "RockellaScraper",
        "chashama":         "ChashamaScraper",
        "spacefinder":      "SpacefinderScraper",
        "loopnet":          "LoopnetScraper",
        "nyfa":             "NyfaScraper",
        "listings_project": "ListingsProjectScraper",
        "craigslist":       "CraigslistScraper",
        "streeteasy":       "StreeteasyScraper",
    }[name]
    return getattr(mod, class_name)


def _make_client_and_config():
    from scraper.client import FirecrawlClient
    from scraper.config import Config
    config = Config()
    config.validate()
    client = FirecrawlClient(config)
    return client, config


# ---------------------------------------------------------------------------
# Reachability tests
# ---------------------------------------------------------------------------

@pytest.mark.reachability
@pytest.mark.parametrize("name,url,restricted", SOURCES, ids=SOURCE_IDS)
def test_reachability(name, url, restricted):
    """
    Assert that the source URL returns an HTTP response.

    Pass:   any response received (even 4xx — site is up, may just block bots)
    Fail:   connection error, DNS failure, timeout, or 5xx server error

    Note: 4xx is treated as reachable because Firecrawl's headless browser
    can often succeed where a plain HTTP client gets blocked.
    """
    try:
        resp = httpx.get(
            url,
            headers=HEADERS,
            follow_redirects=True,
            timeout=REACHABILITY_TIMEOUT,
        )
    except httpx.ConnectError as e:
        pytest.fail(f"{name}: connection error — {e}")
    except httpx.TimeoutException:
        pytest.fail(f"{name}: timed out after {REACHABILITY_TIMEOUT}s")
    except Exception as e:
        pytest.fail(f"{name}: unexpected error — {e}")

    status = resp.status_code

    if status >= 500:
        pytest.fail(f"{name}: server error {status}")

    # Attach info to the test output regardless of pass/fail
    access = "open" if status < 400 else f"blocked ({status}) — Firecrawl may still work"
    restricted_note = " [restricted source]" if restricted else ""
    print(f"\n  {name}{restricted_note}: HTTP {status} — {access}")

    # 4xx is allowed — don't fail, but annotate
    if status == 403:
        pytest.skip(
            reason=f"{name}: returned 403 to plain HTTP — site is up but blocking bots. "
                   "Firecrawl may still succeed. Run live tests to confirm."
        )


# ---------------------------------------------------------------------------
# Data retrieval tests
# ---------------------------------------------------------------------------

def _live_skip_reason():
    if not os.environ.get("FIRECRAWL_API_KEY"):
        return "FIRECRAWL_API_KEY not set — skipping live scraper tests"
    return None


@pytest.mark.live
@pytest.mark.parametrize("name,url,restricted", SOURCES, ids=SOURCE_IDS)
def test_data_retrieval(name, url, restricted):
    """
    Run the real scraper for each source and assert it returns at least one listing.

    Requires: FIRECRAWL_API_KEY set in the environment.
    Uses real Firecrawl credits.

    Pass:   scraper returns >= 1 listing
    Fail:   0 listings returned AND no robots.txt / access-restriction explanation
    Skip:   FIRECRAWL_API_KEY not set, or robots.txt explicitly disallows scraping
    """
    reason = _live_skip_reason()
    if reason:
        pytest.skip(reason)

    try:
        client, config = _make_client_and_config()
    except ValueError as e:
        pytest.skip(str(e))

    cls = _scraper_class(name)
    scraper = cls(client, config)

    result = scraper.run()

    # Robots.txt block is not a test failure — it's expected behavior
    robots_blocked = any("robots.txt" in e for e in result.errors)
    if robots_blocked:
        pytest.skip(f"{name}: robots.txt disallows scraping")

    # Access restrictions (403, etc.) are worth surfacing but not hard failures
    access_blocked = any(
        kw in " ".join(result.errors).lower()
        for kw in ["403", "access", "forbidden", "blocked", "restricted"]
    )

    listing_count = len(result.listings)
    error_summary  = "; ".join(result.errors) if result.errors else "none"
    restricted_note = " [restricted source]" if restricted else ""

    print(
        f"\n  {name}{restricted_note}: "
        f"{listing_count} listing(s), "
        f"{result.credits_used} credit(s) used, "
        f"errors: {error_summary}"
    )

    if listing_count == 0:
        if access_blocked:
            pytest.skip(
                f"{name}: access blocked (0 listings). Errors: {error_summary}"
            )
        else:
            pytest.fail(
                f"{name}: scraper returned 0 listings. Errors: {error_summary}"
            )


# ---------------------------------------------------------------------------
# Standalone runner — reachability summary without pytest
# ---------------------------------------------------------------------------

@dataclass
class ReachResult:
    name: str
    url: str
    status: int | None
    error: str | None
    restricted: bool

    @property
    def reachable(self) -> bool:
        return self.status is not None and self.status < 500

    @property
    def accessible(self) -> bool:
        return self.status is not None and self.status < 400

    def label(self) -> str:
        if self.error:
            return f"UNREACHABLE  ({self.error})"
        if self.accessible:
            return f"OK           HTTP {self.status}"
        if self.reachable:
            return f"BLOCKED      HTTP {self.status} — Firecrawl may still work"
        return f"SERVER ERROR HTTP {self.status}"


def run_reachability_report() -> None:
    results: list[ReachResult] = []

    print("\nStudio Now — Source Reachability Check")
    print("=" * 60)

    for name, url, restricted in SOURCES:
        tag = " [restricted]" if restricted else ""
        print(f"  Checking {name}{tag} ...", end=" ", flush=True)
        t0 = time.monotonic()

        try:
            resp = httpx.get(
                url,
                headers=HEADERS,
                follow_redirects=True,
                timeout=REACHABILITY_TIMEOUT,
            )
            elapsed = time.monotonic() - t0
            r = ReachResult(name, url, resp.status_code, None, restricted)
            print(f"{r.label()}  ({elapsed:.1f}s)")
        except httpx.ConnectError as e:
            r = ReachResult(name, url, None, f"connection error: {e}", restricted)
            print(r.label())
        except httpx.TimeoutException:
            r = ReachResult(name, url, None, f"timed out after {REACHABILITY_TIMEOUT}s", restricted)
            print(r.label())
        except Exception as e:
            r = ReachResult(name, url, None, str(e), restricted)
            print(r.label())

        results.append(r)

    print()
    print("Summary")
    print("-" * 60)

    ok       = [r for r in results if r.accessible]
    blocked  = [r for r in results if r.reachable and not r.accessible]
    down     = [r for r in results if not r.reachable]

    print(f"  Accessible:  {len(ok)}/{len(results)}")
    print(f"  Blocked:     {len(blocked)}/{len(results)}  (reachable but returning 4xx)")
    print(f"  Unreachable: {len(down)}/{len(results)}")

    if blocked:
        print()
        print("Blocked sources (Firecrawl headless browser may still succeed):")
        for r in blocked:
            print(f"  {r.name:20s} {r.url}")

    if down:
        print()
        print("Unreachable sources:")
        for r in down:
            print(f"  {r.name:20s} {r.error}")

    print()


if __name__ == "__main__":
    run_reachability_report()
