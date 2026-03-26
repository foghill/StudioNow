"""
Mana Contemporary — Major studio complex near NYC (Jersey City, NJ).

200+ artist studios, 50+ free/subsidized studios annually.
Studios range from 200-2,000 sq ft.

Website: https://www.manacontemporary.com/studios/
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

STUDIOS_URL = "https://www.manacontemporary.com/studios/"

STUDIO_SCHEMA = {
    "type": "object",
    "properties": {
        "studios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Studio name or program name"},
                    "description": {"type": "string"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string", "description": "Detail page URL"},
                    "availability": {"type": "string"},
                    "studio_type": {"type": "string", "description": "e.g. private, shared, subsidized"},
                },
            },
        },
        "address": {"type": "string", "description": "Building address"},
        "general_amenities": {"type": "array", "items": {"type": "string"}},
    },
}


class ManaContemporaryScraper:
    name = "mana_contemporary"
    domain = "www.manacontemporary.com"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain, "/studios/"):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping /studios/"],
            )

        errors: list[str] = []
        credits_before = self.client.credits_used
        listings: list[StudioListing] = []

        try:
            result = self.client.scrape(
                STUDIOS_URL,
                extract={"schema": STUDIO_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            studios = extracted.get("studios", [])
            building_address = extracted.get("address", "888 Newark Ave, Jersey City, NJ 07306")
            general_amenities = extracted.get("general_amenities", [])

            for studio in studios:
                detail_url = studio.get("url", STUDIOS_URL)
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"https://www.manacontemporary.com{detail_url}"

                listing = StudioListing(
                    source=self.name,
                    source_url=detail_url,
                    title=studio.get("name", "Mana Contemporary Studio"),
                    address=building_address,
                    neighborhood="Jersey City",
                    size_sqft=studio.get("size_sqft"),
                    price_monthly=studio.get("price_monthly"),
                    amenities=studio.get("amenities") or general_amenities,
                    photos=studio.get("photos", []),
                    description=studio.get("description"),
                    use_type=studio.get("studio_type", "studio"),
                )
                slug = (studio.get("name") or "studio").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("Mana Contemporary: found %d studios", len(studios))

        except Exception as e:
            errors.append(f"Scrape failed: {e}")
            logger.error("Mana Contemporary error: %s", e)

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
