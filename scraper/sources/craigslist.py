"""
Craigslist NYC scraper — DISABLED BY DEFAULT.

Craigslist's Terms of Service explicitly prohibit automated scraping.
This source is only enabled when the operator uses --include-restricted.
"""
from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

# Craigslist search URLs for office/commercial spaces in NYC
SEARCH_URLS = [
    "https://newyork.craigslist.org/search/off#search=1~list~0~0",  # office/commercial
]

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Post title"},
                    "address": {"type": "string", "description": "Location or address"},
                    "neighborhood": {"type": "string", "description": "Neighborhood"},
                    "price_monthly": {"type": "number", "description": "Monthly price"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "description": {"type": "string", "description": "Post body text"},
                    "url": {"type": "string", "description": "Post URL"},
                    "photos": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


class CraigslistScraper:
    name = "craigslist"
    domain = "newyork.craigslist.org"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        logger.warning(
            "Craigslist scraping may violate their Terms of Service. "
            "Use at your own discretion."
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
                    # Filter for studio/art-related posts
                    title = (raw.get("title") or "").lower()
                    desc = (raw.get("description") or "").lower()
                    combined = f"{title} {desc}"
                    is_relevant = any(
                        kw in combined
                        for kw in ["studio", "art", "artist", "creative", "workshop", "maker"]
                    )
                    if not is_relevant:
                        continue

                    detail_url = raw.get("url", url)
                    listing = StudioListing(
                        source=self.name,
                        source_url=detail_url,
                        title=raw.get("title", "Craigslist Listing"),
                        address=raw.get("address"),
                        neighborhood=raw.get("neighborhood"),
                        size_sqft=raw.get("size_sqft"),
                        price_monthly=raw.get("price_monthly"),
                        photos=raw.get("photos", []),
                        description=raw.get("description"),
                        use_type="commercial",
                    )
                    slug = (raw.get("title") or "post").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)

                logger.info("Craigslist %s: found %d relevant listings", url, len(raw_listings))

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")
                logger.error("Craigslist error on %s: %s", url, e)

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
