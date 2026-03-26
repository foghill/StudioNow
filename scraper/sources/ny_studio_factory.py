"""
NY Studio Factory — Dedicated artist studio rental building in Brooklyn.

Website: https://www.nystudiofactory.com/
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nystudiofactory.com/"

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Studio name or number"},
                    "address": {"type": "string", "description": "Building address"},
                    "neighborhood": {"type": "string", "description": "NYC neighborhood"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent in USD"},
                    "description": {"type": "string", "description": "Studio description"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "availability": {"type": "string", "description": "Availability status"},
                    "url": {"type": "string", "description": "Listing detail URL"},
                },
            },
        },
        "building_address": {"type": "string", "description": "Main building address"},
        "building_amenities": {"type": "array", "items": {"type": "string"}},
    },
}


class NyStudioFactoryScraper:
    name = "ny_studio_factory"
    domain = "www.nystudiofactory.com"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

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
                BASE_URL,
                extract={"schema": LISTING_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            raw_listings = extracted.get("listings", [])
            building_address = extracted.get("building_address")
            building_amenities = extracted.get("building_amenities", [])

            for raw in raw_listings:
                listing = StudioListing(
                    source=self.name,
                    source_url=raw.get("url", BASE_URL),
                    title=raw.get("title", "NY Studio Factory Space"),
                    address=raw.get("address") or building_address,
                    neighborhood=raw.get("neighborhood"),
                    size_sqft=raw.get("size_sqft"),
                    price_monthly=raw.get("price_monthly"),
                    photos=raw.get("photos", []),
                    amenities=raw.get("amenities") or building_amenities,
                    description=raw.get("description"),
                    use_type="studio",
                )
                slug = (raw.get("title") or "space").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("NY Studio Factory: found %d listings", len(raw_listings))

        except Exception as e:
            errors.append(f"Scrape failed: {e}")
            logger.error("NY Studio Factory error: %s", e)

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
