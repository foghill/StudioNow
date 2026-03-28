"""
NYC Open Data — DCLA Cultural Organizations dataset.

Uses the free Socrata REST API to pull cultural organization data from NYC's
Department of Cultural Affairs. No Firecrawl credits needed.

API: https://data.cityofnewyork.us/resource/u35m-9t32.json
"""
from __future__ import annotations

import logging

import os

import httpx

from ..config import Config
from ..models import Borough, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

# Socrata API endpoint for DCLA Cultural Organizations
API_URL = "https://data.cityofnewyork.us/resource/u35m-9t32.json"

# NYC Open Data app token — read at scrape time so Railway env var updates take effect
# Get yours free at: https://data.cityofnewyork.us/profile/edit/developer_settings

# SoQL query: filter for organizations related to studio/art/workspace
# $where filters by discipline containing relevant keywords
# $limit caps results to avoid huge payloads
SOQL_PARAMS = {
    "$limit": 1000,
    "$where": (
        "discipline like '%Visual%' OR "
        "discipline like '%Multi%' OR "
        "discipline like '%Media%' OR "
        "discipline like '%Craft%' OR "
        "discipline like '%Design%' OR "
        "discipline like '%Photography%'"
    ),
}

BOROUGH_MAP = {
    "manhattan": Borough.MANHATTAN,
    "brooklyn": Borough.BROOKLYN,
    "queens": Borough.QUEENS,
    "bronx": Borough.BRONX,
    "staten island": Borough.STATEN_ISLAND,
    "x": Borough.MANHATTAN,
    "m": Borough.MANHATTAN,
    "bk": Borough.BROOKLYN,
    "bx": Borough.BRONX,
    "q": Borough.QUEENS,
    "si": Borough.STATEN_ISLAND,
}


class NycOpendataScraper:
    name = "nyc_opendata"
    domain = "data.cityofnewyork.us"

    def __init__(self, client=None, config: Config | None = None):
        # client is accepted for interface compatibility but not used (no Firecrawl)
        self.config = config or Config()

    def scrape(self) -> ScraperResult:
        errors: list[str] = []
        listings: list[StudioListing] = []

        try:
            headers = {"Accept": "application/json"}
            app_token = os.environ.get("NYC_OPENDATA_APP_TOKEN", "")
            secret_key = os.environ.get("NYC_OPENDATA_SECRET_KEY", "")
            # Socrata auth: app token + secret key via HTTP Basic auth
            auth = None
            if app_token and secret_key:
                auth = httpx.BasicAuth(app_token, secret_key)
                logger.info("Using NYC Open Data authenticated access (app token + secret key)")
            elif app_token:
                headers["X-App-Token"] = app_token
                logger.info("Using NYC Open Data app token (unauthenticated, higher rate limit)")
            else:
                logger.warning("No NYC_OPENDATA_APP_TOKEN set — request may be rate-limited")

            resp = httpx.get(
                API_URL,
                params=SOQL_PARAMS,
                timeout=30,
                headers=headers,
                auth=auth,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("NYC Open Data: received %d records", len(data))
        except Exception as e:
            return ScraperResult(
                source=self.name,
                errors=[f"API request failed: {e}"],
            )

        for record in data:
            org_name = record.get("organization_name", "").strip()
            if not org_name:
                continue

            # Build address from available fields
            address_parts = []
            if record.get("address"):
                address_parts.append(record["address"])
            if record.get("city"):
                address_parts.append(record["city"])
            if record.get("state"):
                address_parts.append(record["state"])
            if record.get("zip"):
                address_parts.append(record["zip"])
            address = ", ".join(address_parts) if address_parts else None

            # Parse borough
            borough_raw = (record.get("borough") or record.get("city") or "").lower().strip()
            borough = BOROUGH_MAP.get(borough_raw)

            # Extract coordinates if available
            lat = None
            lng = None
            if record.get("latitude"):
                try:
                    lat = float(record["latitude"])
                except (ValueError, TypeError):
                    pass
            if record.get("longitude"):
                try:
                    lng = float(record["longitude"])
                except (ValueError, TypeError):
                    pass

            # Build a description from discipline and other fields
            discipline = record.get("discipline", "")
            description = f"Cultural organization: {discipline}" if discipline else None

            # Source URL — link to the org's row on NYC Open Data
            source_url = f"https://data.cityofnewyork.us/resource/u35m-9t32.json?organization_name={org_name.replace(' ', '%20')}"

            listing = StudioListing(
                source=self.name,
                source_url=source_url,
                title=org_name,
                address=address,
                neighborhood=record.get("city") or record.get("borough"),
                borough=borough,
                latitude=lat,
                longitude=lng,
                description=description,
                use_type=f"cultural-org ({discipline})" if discipline else "cultural-org",
            )
            slug = org_name.replace(" ", "-").lower()[:50]
            listing.id = f"{self.name}-{slug}"
            listing.source_id = slug
            listings.append(listing)

        return ScraperResult(
            source=self.name,
            listings=listings,
            credits_used=0,  # No Firecrawl credits used
            errors=errors,
        )

    def run(self) -> ScraperResult:
        logger.info("Starting scraper: %s (API-based, no Firecrawl credits)", self.name)
        try:
            result = self.scrape()
            logger.info(
                "%s: collected %d listings, %d errors",
                self.name,
                len(result.listings),
                len(result.errors),
            )
            return result
        except Exception as e:
            logger.error("%s: fatal error: %s", self.name, e)
            return ScraperResult(source=self.name, errors=[f"Fatal: {e}"])
