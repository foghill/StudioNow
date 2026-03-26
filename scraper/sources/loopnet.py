from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

# LoopNet search URLs for artist-relevant commercial spaces in NYC
SEARCH_URLS = [
    "https://www.loopnet.com/search/commercial-real-estate/new-york-ny/for-lease/?sk=4f2302d82ce93f0cfafe6d4dc3a90e57&e=u",
    "https://www.loopnet.com/search/listings/live-work-space/ny/for-lease/",
]

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Property name or listing title"},
                    "address": {"type": "string", "description": "Full address"},
                    "neighborhood": {"type": "string", "description": "Neighborhood or area"},
                    "size_sqft": {"type": "integer", "description": "Available square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent in USD"},
                    "price_per_sqft": {"type": "number", "description": "Annual price per square foot"},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "property_type": {"type": "string", "description": "e.g. creative/loft, flex, office"},
                    "url": {"type": "string", "description": "Listing detail URL"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
            },
        }
    },
}


class LoopnetScraper:
    name = "loopnet"
    domain = "www.loopnet.com"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain, "/search/"):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping /search/"],
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
                    # Estimate monthly price from per-sqft annual if needed
                    price = raw.get("price_monthly")
                    if not price and raw.get("price_per_sqft") and raw.get("size_sqft"):
                        price = (raw["price_per_sqft"] * raw["size_sqft"]) / 12

                    detail_url = raw.get("url", url)
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = f"https://www.loopnet.com{detail_url}"

                    listing = StudioListing(
                        source=self.name,
                        source_url=detail_url,
                        title=raw.get("title", "LoopNet Listing"),
                        address=raw.get("address"),
                        neighborhood=raw.get("neighborhood"),
                        size_sqft=raw.get("size_sqft"),
                        price_monthly=price,
                        photos=raw.get("photos", []),
                        amenities=raw.get("amenities", []),
                        description=raw.get("description"),
                        use_type=raw.get("property_type", "commercial"),
                    )
                    slug = (raw.get("title") or "listing").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)

                logger.info("LoopNet %s: found %d listings", url, len(raw_listings))

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")
                logger.error("LoopNet error on %s: %s", url, e)

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
