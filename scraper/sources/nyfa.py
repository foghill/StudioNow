from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

INDEX_URL = "https://www.nyfa.org/spaces/"

SPACE_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Space or studio name"},
                    "address": {"type": "string", "description": "Address or location"},
                    "neighborhood": {"type": "string", "description": "NYC neighborhood"},
                    "description": {"type": "string", "description": "Listing description"},
                    "size_sqft": {"type": "integer", "description": "Square footage"},
                    "price_monthly": {"type": "number", "description": "Monthly rent in USD"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "photos": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string", "description": "Link to listing"},
                    "space_type": {"type": "string", "description": "studio, rehearsal, etc."},
                },
            },
        }
    },
}


class NyfaScraper:
    name = "nyfa"
    domain = "www.nyfa.org"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain, "/spaces/"):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping /spaces/"],
            )

        errors: list[str] = []
        credits_before = self.client.credits_used
        listings: list[StudioListing] = []

        # Try scraping the index page — NYFA returned 403 in research,
        # but Firecrawl's headless browser may succeed
        try:
            result = self.client.scrape(
                INDEX_URL,
                extract={"schema": SPACE_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            raw_listings = extracted.get("listings", [])

            for raw in raw_listings:
                detail_url = raw.get("url", INDEX_URL)
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"https://www.nyfa.org{detail_url}"

                listing = StudioListing(
                    source=self.name,
                    source_url=detail_url,
                    title=raw.get("title", "NYFA Space"),
                    address=raw.get("address"),
                    neighborhood=raw.get("neighborhood"),
                    size_sqft=raw.get("size_sqft"),
                    price_monthly=raw.get("price_monthly"),
                    photos=raw.get("photos", []),
                    amenities=raw.get("amenities", []),
                    description=raw.get("description"),
                    use_type=raw.get("space_type", "studio"),
                )
                slug = (raw.get("title") or "space").replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            logger.info("NYFA: found %d listings from index", len(raw_listings))

        except Exception as e:
            errors.append(f"Index scrape failed (may be access-restricted): {e}")
            logger.warning("NYFA index scrape failed: %s", e)

        # If index failed, try Firecrawl search as fallback
        if not listings:
            try:
                logger.info("NYFA: falling back to Firecrawl search")
                result = self.client.search(
                    "NYFA artist studio space rental NYC",
                    limit=10,
                )
                data = result.get("data", []) if isinstance(result, dict) else []
                for item in data:
                    url = item.get("url", "")
                    if "nyfa.org" not in url:
                        continue
                    metadata = item.get("metadata", {})
                    listing = StudioListing(
                        source=self.name,
                        source_url=url,
                        title=metadata.get("title", "NYFA Space"),
                        description=metadata.get("description"),
                        use_type="studio",
                    )
                    slug = metadata.get("title", "space").replace(" ", "-").lower()[:50]
                    listing.id = f"{self.name}-{slug}"
                    listings.append(listing)

            except Exception as e:
                errors.append(f"Search fallback also failed: {e}")

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
