"""
StreetEasy scraper — DISABLED BY DEFAULT.

StreetEasy (owned by Zillow) has strong anti-scraping measures.
Primarily residential, but includes live-work loft spaces.
Enabled only with --include-restricted.
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

SEARCH_URLS = [
    "https://streeteasy.com/for-rent/nyc/status:open%7Cprice:-2500%7Carea:300-?sort_by=listed_desc",
]

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Listing title"},
                    "address": {"type": "string", "description": "Full address"},
                    "neighborhood": {"type": "string", "description": "Neighborhood"},
                    "price_monthly": {"type": "number", "description": "Monthly rent"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "bedrooms": {"type": "integer"},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string", "description": "Listing URL"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
            },
        }
    },
}


class StreeteasyScraper:
    name = "streeteasy"
    domain = "streeteasy.com"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        logger.warning(
            "StreetEasy has aggressive anti-scraping. Results may be limited."
        )

        listings: list[StudioListing] = []
        errors: list[str] = []
        credits_before = self.client.credits_used

        for url in SEARCH_URLS:
            try:
                result = self.client.scrape(
                    url,
                    extract={"schema": LISTING_SCHEMA},
                )
                extracted = result.get("extract", {}) if isinstance(result, dict) else {}
                raw_listings = extracted.get("listings", [])

                for raw in raw_listings:
                    detail_url = raw.get("url", url)
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = f"https://streeteasy.com{detail_url}"

                    listing = StudioListing(
                        source=self.name,
                        source_url=detail_url,
                        title=raw.get("title", "StreetEasy Listing"),
                        address=raw.get("address"),
                        neighborhood=raw.get("neighborhood"),
                        size_sqft=raw.get("size_sqft"),
                        price_monthly=raw.get("price_monthly"),
                        photos=raw.get("photos", []),
                        amenities=raw.get("amenities", []),
                        description=raw.get("description"),
                        use_type="residential-studio",
                    )
                    slug = (raw.get("address") or "listing").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)

                logger.info("StreetEasy: found %d listings", len(raw_listings))

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")
                logger.error("StreetEasy error: %s", e)

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
                self.name,
                len(result.listings),
                len(result.errors),
                result.credits_used,
            )
            return result
        except Exception as e:
            logger.error("%s: fatal error: %s", self.name, e)
            return ScraperResult(source=self.name, errors=[f"Fatal: {e}"])
