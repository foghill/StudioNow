"""
Pioneer Works — Arts center in Red Hook, Brooklyn.

25,000 sq ft warehouse facility with 50+ resident artists/scientists per year.
Equipment includes 3D printer, metalworking, woodworking, recording studios.

Website: https://pioneerworks.org/
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://pioneerworks.org/"

SPACE_SCHEMA = {
    "type": "object",
    "properties": {
        "spaces": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Program or space name"},
                    "description": {"type": "string"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                    "program_type": {"type": "string", "description": "residency, studio, workshop, etc."},
                },
            },
        },
        "address": {"type": "string"},
        "facility_amenities": {"type": "array", "items": {"type": "string"}},
    },
}


class PioneerWorksScraper:
    name = "pioneer_works"
    domain = "pioneerworks.org"

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
                extract={"schema": SPACE_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            spaces = extracted.get("spaces", [])
            address = extracted.get("address", "159 Pioneer St, Brooklyn, NY 11231")
            facility_amenities = extracted.get("facility_amenities", [])

            for space in spaces:
                detail_url = space.get("url", BASE_URL)
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"https://pioneerworks.org{detail_url}"

                listing = StudioListing(
                    source=self.name,
                    source_url=detail_url,
                    title=space.get("name", "Pioneer Works Space"),
                    address=address,
                    neighborhood="Red Hook",
                    borough="brooklyn",
                    amenities=space.get("amenities") or facility_amenities,
                    photos=space.get("photos", []),
                    description=space.get("description"),
                    use_type=space.get("program_type", "residency/studio"),
                )
                slug = (space.get("name") or "space").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("Pioneer Works: found %d spaces", len(spaces))

        except Exception as e:
            errors.append(f"Scrape failed: {e}")
            logger.error("Pioneer Works error: %s", e)

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
