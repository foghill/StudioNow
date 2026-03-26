"""
Brooklyn Navy Yard — Major artist studio hub with 300+ acres.

Website: https://www.brooklynnavyyard.org/
Tenant directory: https://www.brooklynnavyyard.org/?post_type=tenant
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

TENANT_URL = "https://www.brooklynnavyyard.org/?post_type=tenant"
BASE_URL = "https://www.brooklynnavyyard.org"

TENANT_SCHEMA = {
    "type": "object",
    "properties": {
        "tenants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tenant/studio name"},
                    "description": {"type": "string", "description": "Description of the space/business"},
                    "category": {"type": "string", "description": "Category: art studio, maker space, etc."},
                    "building": {"type": "string", "description": "Building number or name"},
                    "url": {"type": "string", "description": "Link to tenant page"},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "website": {"type": "string", "description": "External website"},
                },
            },
        }
    },
}

ARTIST_KEYWORDS = [
    "studio", "art", "artist", "gallery", "design", "creative",
    "maker", "craft", "photo", "film", "music", "ceramic",
    "sculpture", "paint", "print", "fabricat", "woodwork", "metal",
]


class NavyYardScraper:
    name = "navy_yard"
    domain = "www.brooklynnavyyard.org"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def _is_artist_relevant(self, tenant: dict) -> bool:
        combined = " ".join([
            tenant.get("name", ""),
            tenant.get("description", ""),
            tenant.get("category", ""),
        ]).lower()
        return any(kw in combined for kw in ARTIST_KEYWORDS)

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping"],
            )

        errors: list[str] = []
        credits_before = self.client.credits_used
        listings: list[StudioListing] = []

        try:
            result = self.client.scrape(
                TENANT_URL,
                extract={"schema": TENANT_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            tenants = extracted.get("tenants", [])

            for tenant in tenants:
                if not self._is_artist_relevant(tenant):
                    continue

                detail_url = tenant.get("url", TENANT_URL)
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"{BASE_URL}{detail_url}"

                listing = StudioListing(
                    source=self.name,
                    source_url=detail_url,
                    title=tenant.get("name", "Navy Yard Studio"),
                    address=f"Brooklyn Navy Yard, {tenant.get('building', 'Brooklyn, NY 11205')}",
                    neighborhood="Brooklyn Navy Yard",
                    borough="brooklyn",
                    photos=tenant.get("photos", []),
                    description=tenant.get("description"),
                    use_type=tenant.get("category", "studio"),
                )
                slug = (tenant.get("name") or "tenant").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("Navy Yard: found %d artist-relevant tenants out of %d total", len(listings), len(tenants))

        except Exception as e:
            errors.append(f"Scrape failed: {e}")
            logger.error("Navy Yard error: %s", e)

        credits_used = self.client.credits_used - credits_before
        return ScraperResult(
            source=self.name,
            listings=listings,
            credits_used=credits_used,
            errors=errors,
        )

    def run(self) -> ScraperResult:
        logger.info("Starting scraper: %s", self.name)
        try:
            result = self.scrape()
            logger.info(
                "%s: collected %d listings, %d errors, %d credits",
                self.name, len(result.listings), len(result.errors), result.credits_used,
            )
            return result
        except Exception as e:
            logger.error("%s: fatal error: %s", self.name, e)
            return ScraperResult(source=self.name, errors=[f"Fatal: {e}"])
