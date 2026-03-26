"""
Industry City — Large creative campus in Sunset Park, Brooklyn.

16-building, 6-million-square-foot campus with creative/maker spaces,
studios, and workshops in Sunset Park, Brooklyn.

Website: https://industrycity.com/
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://industrycity.com/"
LEASING_URL = "https://industrycity.com/leasing/"

SPACE_SCHEMA = {
    "type": "object",
    "properties": {
        "spaces": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Space or suite name"},
                    "address": {"type": "string", "description": "Building address or number"},
                    "size_sqft": {"type": "integer", "description": "Available square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent"},
                    "price_per_sqft": {"type": "number", "description": "Annual price per sq ft"},
                    "description": {"type": "string"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                    "space_type": {"type": "string", "description": "office, studio, maker, retail, etc."},
                },
            },
        },
        "campus_address": {"type": "string"},
        "campus_amenities": {"type": "array", "items": {"type": "string"}},
    },
}


class IndustryCityScraper:
    name = "industry_city"
    domain = "industrycity.com"

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

        # Try the leasing page first, fall back to main page
        for url in [LEASING_URL, BASE_URL]:
            try:
                result = self.client.scrape(
                    url,
                    extract={"schema": SPACE_SCHEMA},
                )
                extracted = result.get("extract", {}) if isinstance(result, dict) else {}
                spaces = extracted.get("spaces", [])
                campus_address = extracted.get("campus_address", "220 36th St, Brooklyn, NY 11232")
                campus_amenities = extracted.get("campus_amenities", [])

                for space in spaces:
                    # Estimate monthly price from per-sqft annual if needed
                    price = space.get("price_monthly")
                    if not price and space.get("price_per_sqft") and space.get("size_sqft"):
                        price = (space["price_per_sqft"] * space["size_sqft"]) / 12

                    detail_url = space.get("url", url)
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = f"https://industrycity.com{detail_url}"

                    listing = StudioListing(
                        source=self.name,
                        source_url=detail_url,
                        title=space.get("name", "Industry City Space"),
                        address=space.get("address") or campus_address,
                        neighborhood="Sunset Park",
                        borough="brooklyn",
                        size_sqft=space.get("size_sqft"),
                        price_monthly=price,
                        amenities=space.get("amenities") or campus_amenities,
                        photos=space.get("photos", []),
                        description=space.get("description"),
                        use_type=space.get("space_type", "creative/maker"),
                    )
                    slug = (space.get("name") or "space").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)

                if listings:
                    logger.info("Industry City (%s): found %d spaces", url, len(spaces))
                    break  # Got results, no need to try the other URL

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")
                logger.error("Industry City error on %s: %s", url, e)

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
