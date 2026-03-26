"""
Greenpoint Manufacturing and Design Center (GMDC) — Artist-focused not-for-profit.

8 rehabilitated buildings with 366,000 sq ft of space for woodworkers,
metal workers, ceramic artists, and fine artists in Greenpoint, Brooklyn.

Website: https://gmdconline.org/
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://gmdconline.org/"

BUILDING_SCHEMA = {
    "type": "object",
    "properties": {
        "buildings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Building name or number"},
                    "address": {"type": "string", "description": "Street address"},
                    "description": {"type": "string", "description": "Building description"},
                    "size_sqft": {"type": "integer", "description": "Total or available square footage"},
                    "tenant_types": {"type": "array", "items": {"type": "string"}, "description": "Types of tenants/uses"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string", "description": "Detail page URL"},
                    "available_spaces": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "size_sqft": {"type": "integer"},
                                "price_monthly": {"type": "number"},
                                "description": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "organization_description": {"type": "string"},
    },
}


class GmdcScraper:
    name = "gmdc"
    domain = "gmdconline.org"

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

        # Step 1: Scrape main page for building overview
        try:
            result = self.client.scrape(
                BASE_URL,
                extract={"schema": BUILDING_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            buildings = extracted.get("buildings", [])

            for building in buildings:
                address = building.get("address")
                amenities = building.get("amenities", [])
                photos = building.get("photos", [])

                # If the building has specific available spaces, create a listing per space
                available = building.get("available_spaces", [])
                if available:
                    for space in available:
                        listing = StudioListing(
                            source=self.name,
                            source_url=building.get("url", BASE_URL),
                            title=space.get("name") or f"GMDC {building.get('name', 'Space')}",
                            address=address,
                            neighborhood="Greenpoint",
                            borough="brooklyn",
                            size_sqft=space.get("size_sqft"),
                            price_monthly=space.get("price_monthly"),
                            amenities=amenities,
                            photos=photos,
                            description=space.get("description") or building.get("description"),
                            use_type="studio/workshop",
                        )
                        slug = (space.get("name") or building.get("name", "space")).replace(" ", "-").lower()[:50]
                        listing.id = f"{self.name}-{slug}"
                        listing.source_id = slug
                        listings.append(listing)
                else:
                    # Create one listing per building
                    listing = StudioListing(
                        source=self.name,
                        source_url=building.get("url", BASE_URL),
                        title=f"GMDC {building.get('name', 'Building')}",
                        address=address,
                        neighborhood="Greenpoint",
                        borough="brooklyn",
                        size_sqft=building.get("size_sqft"),
                        amenities=amenities,
                        photos=photos,
                        description=building.get("description"),
                        use_type=", ".join(building.get("tenant_types", ["studio/workshop"])),
                    )
                    slug = building.get("name", "building").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)

            logger.info("GMDC: found %d listings from %d buildings", len(listings), len(buildings))

        except Exception as e:
            errors.append(f"Scrape failed: {e}")
            logger.error("GMDC error: %s", e)

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
