from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

INDEX_URL = "https://chashama.org/programs/space-to-create/"

# Schema tailored for ChaShaMa's location pages
LOCATION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Location name"},
        "address": {"type": "string", "description": "Full street address"},
        "neighborhood": {"type": "string", "description": "NYC neighborhood"},
        "description": {"type": "string", "description": "Space description"},
        "amenities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Available amenities",
        },
        "photos": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Photo URLs",
        },
        "size_sqft": {"type": "integer", "description": "Size in square feet if listed"},
        "price_monthly": {"type": "number", "description": "Monthly cost if listed"},
        "use_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Types of use: workspace, studio, gallery, rehearsal, etc.",
        },
        "latitude": {"type": "number"},
        "longitude": {"type": "number"},
    },
}


class ChashamaScraper:
    name = "chashama"
    domain = "chashama.org"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def _discover_location_urls(self) -> list[str]:
        """Use Firecrawl map to discover all location pages."""
        try:
            urls = self.client.map_url(INDEX_URL)
            # Filter to location/space detail pages
            location_urls = [
                u for u in urls
                if "/location/" in u or "/space/" in u or "/programs/space-to-create/" in u
            ]
            # Also grab any that look like individual space pages
            location_urls = list(set(location_urls))
            logger.info("ChaShaMa: discovered %d location URLs", len(location_urls))
            return location_urls[:20]  # Cap at 20 to conserve credits
        except Exception as e:
            logger.error("ChaShaMa: map failed: %s", e)
            return [INDEX_URL]

    def _scrape_index(self) -> list[dict]:
        """Scrape the main space-to-create index page for listing overviews."""
        try:
            result = self.client.scrape(
                INDEX_URL,
                extract={"schema": FIRECRAWL_EXTRACT_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            return extracted.get("listings", [])
        except Exception as e:
            logger.error("ChaShaMa index scrape failed: %s", e)
            return []

    def _scrape_location(self, url: str) -> dict | None:
        """Scrape a single location detail page."""
        try:
            result = self.client.scrape(
                url,
                extract={"schema": LOCATION_SCHEMA},
            )
            extracted = result.get("extract", {}) if isinstance(result, dict) else {}
            if extracted.get("name") or extracted.get("address"):
                extracted["source_url"] = url
                return extracted
            return None
        except Exception as e:
            logger.error("ChaShaMa location scrape failed (%s): %s", url, e)
            return None

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping"],
            )

        errors: list[str] = []
        credits_before = self.client.credits_used

        # Step 1: Discover location URLs
        location_urls = self._discover_location_urls()

        # Step 2: Scrape index page for overview
        index_listings = self._scrape_index()
        logger.info("ChaShaMa index: found %d listing overviews", len(index_listings))

        # Step 3: Scrape individual location pages
        locations: list[dict] = []
        for url in location_urls:
            if url == INDEX_URL:
                continue
            loc = self._scrape_location(url)
            if loc:
                locations.append(loc)

        # Build StudioListing objects — prefer location detail data, fall back to index
        all_listings: list[StudioListing] = []

        # From location detail pages
        for loc in locations:
            use_types = loc.get("use_types", [])
            # Filter to workspace/studio types
            is_workspace = any(
                t.lower() in ("workspace", "studio", "artist studio", "creative space")
                for t in use_types
            ) if use_types else True  # Include if no type info

            if not is_workspace:
                continue

            listing = StudioListing(
                source=self.name,
                source_url=loc.get("source_url", INDEX_URL),
                title=loc.get("name", "ChaShaMa Space"),
                address=loc.get("address"),
                neighborhood=loc.get("neighborhood"),
                size_sqft=loc.get("size_sqft"),
                price_monthly=loc.get("price_monthly"),
                photos=loc.get("photos", []),
                amenities=loc.get("amenities", []),
                description=loc.get("description"),
                use_type=", ".join(use_types) if use_types else "studio",
                latitude=loc.get("latitude"),
                longitude=loc.get("longitude"),
            )
            slug = loc.get("name", "unknown").replace(" ", "-").lower()
            listing.id = f"{self.name}-{slug}"
            listing.source_id = slug
            all_listings.append(listing)

        # From index (for any not already covered by detail pages)
        detail_titles = {l.title.lower().strip() for l in all_listings}
        for raw in index_listings:
            title = raw.get("title", "").strip()
            if title.lower() in detail_titles:
                continue
            listing = StudioListing(
                source=self.name,
                source_url=raw.get("url", INDEX_URL),
                title=title or "ChaShaMa Space",
                address=raw.get("address"),
                neighborhood=raw.get("neighborhood"),
                size_sqft=raw.get("size_sqft"),
                price_monthly=raw.get("price_monthly"),
                photos=raw.get("photos", []),
                amenities=raw.get("amenities", []),
                description=raw.get("description"),
                use_type=raw.get("use_type", "studio"),
            )
            slug = title.replace(" ", "-").lower() or "unknown"
            listing.id = f"{self.name}-{slug}"
            listing.source_id = slug
            all_listings.append(listing)

        credits_used = self.client.credits_used - credits_before

        return ScraperResult(
            source=self.name,
            listings=all_listings,
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
