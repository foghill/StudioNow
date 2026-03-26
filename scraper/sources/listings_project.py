from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.listingsproject.com"

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Listing title"},
                    "address": {"type": "string", "description": "Location or address"},
                    "neighborhood": {"type": "string", "description": "NYC neighborhood"},
                    "description": {"type": "string", "description": "Full listing text"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent"},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string", "description": "Listing URL"},
                    "category": {"type": "string", "description": "workspace, studio, sublet, etc."},
                },
            },
        }
    },
}


class ListingsProjectScraper:
    name = "listings_project"
    domain = "www.listingsproject.com"

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

        # Step 1: Discover listing URLs via map
        try:
            urls = self.client.map_url(BASE_URL)
            listing_urls = [
                u for u in urls
                if "/listing/" in u or "/browse/" in u
            ]
            listing_urls = list(set(listing_urls))[:15]
            logger.info("Listings Project: discovered %d relevant URLs", len(listing_urls))
        except Exception as e:
            errors.append(f"Map failed: {e}")
            listing_urls = []

        # Step 2: Try scraping the main page for NYC workspace listings
        try:
            result = self.client.scrape(
                BASE_URL,
                extract={"schema": LISTING_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            raw_listings = extracted.get("listings", [])

            for raw in raw_listings:
                category = (raw.get("category") or "").lower()
                title = (raw.get("title") or "").lower()
                desc = (raw.get("description") or "").lower()
                # Filter for workspace/studio relevant listings
                combined = f"{category} {title} {desc}"
                if not any(kw in combined for kw in ["studio", "workspace", "art", "creative", "office"]):
                    continue

                detail_url = raw.get("url", BASE_URL)
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"{BASE_URL}{detail_url}"

                listing = StudioListing(
                    source=self.name,
                    source_url=detail_url,
                    title=raw.get("title", "Listings Project Space"),
                    address=raw.get("address"),
                    neighborhood=raw.get("neighborhood"),
                    size_sqft=raw.get("size_sqft"),
                    price_monthly=raw.get("price_monthly"),
                    photos=raw.get("photos", []),
                    description=raw.get("description"),
                    use_type=raw.get("category", "studio"),
                )
                slug = (raw.get("title") or "listing").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("Listings Project index: found %d relevant listings", len(listings))

        except Exception as e:
            errors.append(f"Index scrape failed: {e}")
            logger.error("Listings Project error: %s", e)

        # Step 3: Scrape individual listing pages if we found any
        for url in listing_urls[:10]:
            try:
                result = self.client.scrape(
                    url,
                    extract={
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "address": {"type": "string"},
                                "neighborhood": {"type": "string"},
                                "description": {"type": "string"},
                                "size_sqft": {"type": "integer"},
                                "price_monthly": {"type": "number"},
                                "photos": {"type": "array", "items": {"type": "string"}},
                                "category": {"type": "string"},
                            },
                        }
                    },
                )
                extracted = result.get("extract", {}) if isinstance(result, dict) else {}
                if extracted.get("title"):
                    listing = StudioListing(
                        source=self.name,
                        source_url=url,
                        title=extracted.get("title", "Space"),
                        address=extracted.get("address"),
                        neighborhood=extracted.get("neighborhood"),
                        size_sqft=extracted.get("size_sqft"),
                        price_monthly=extracted.get("price_monthly"),
                        photos=extracted.get("photos", []),
                        description=extracted.get("description"),
                        use_type=extracted.get("category", "studio"),
                    )
                    slug = extracted["title"].replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listing.source_id = slug
                    listings.append(listing)
            except Exception as e:
                errors.append(f"Detail scrape failed ({url}): {e}")

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
