from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

BASE_URL = "https://nyc.spacefinder.org"
SPACES_URL = f"{BASE_URL}/spaces"

# Spacefinder space types relevant to artist studios
RELEVANT_KEYWORDS = [
    "studio",
    "art",
    "artist",
    "creative",
    "workshop",
    "maker",
    "rehearsal",
    "practice",
    "workspace",
]

SPACE_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Space name"},
        "address": {"type": "string", "description": "Full street address"},
        "neighborhood": {"type": "string", "description": "NYC neighborhood"},
        "description": {"type": "string", "description": "Space description"},
        "size_sqft": {"type": "integer", "description": "Size in square feet"},
        "price_hourly": {"type": "number", "description": "Hourly rate if listed"},
        "price_daily": {"type": "number", "description": "Daily rate if listed"},
        "price_monthly": {"type": "number", "description": "Monthly rate if listed"},
        "amenities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Available amenities and features",
        },
        "photos": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Photo URLs",
        },
        "space_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Types: studio art, rehearsal, performance, etc.",
        },
        "availability": {"type": "string", "description": "Availability info"},
    },
}


class SpacefinderScraper:
    name = "spacefinder"
    domain = "nyc.spacefinder.org"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def _discover_space_urls(self) -> list[str]:
        """Use map to discover space detail URLs."""
        try:
            urls = self.client.map_url(SPACES_URL)
            space_urls = [u for u in urls if "/spaces/" in u and u != SPACES_URL]
            # Remove duplicates, keep unique detail pages
            space_urls = list(set(space_urls))
            logger.info("Spacefinder: discovered %d space URLs", len(space_urls))
            return space_urls
        except Exception as e:
            logger.error("Spacefinder map failed: %s", e)
            return []

    def _is_relevant(self, url: str, data: dict | None = None) -> bool:
        """Check if a space URL looks relevant to artist studios."""
        url_lower = url.lower()
        if any(kw in url_lower for kw in RELEVANT_KEYWORDS):
            return True
        if data:
            types = data.get("space_types", [])
            desc = (data.get("description") or "").lower()
            name = (data.get("name") or "").lower()
            combined = " ".join(types).lower() + " " + desc + " " + name
            if any(kw in combined for kw in RELEVANT_KEYWORDS):
                return True
        return False

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping"],
            )

        errors: list[str] = []
        credits_before = self.client.credits_used

        # Step 1: Discover URLs
        all_urls = self._discover_space_urls()
        if not all_urls:
            # Fallback: try scraping the main listing page directly
            errors.append("Map returned no URLs, falling back to index scrape")
            all_urls = [SPACES_URL]

        # Step 2: Filter to potentially relevant URLs and cap at 60 to conserve credits
        relevant_urls = [u for u in all_urls if self._is_relevant(u)]
        if not relevant_urls:
            relevant_urls = all_urls[:60]
        else:
            relevant_urls = relevant_urls[:60]

        logger.info("Spacefinder: scraping %d of %d discovered URLs", len(relevant_urls), len(all_urls))

        # Step 3: Scrape individual space pages
        listings: list[StudioListing] = []
        for url in relevant_urls:
            try:
                result = self.client.scrape(
                    url,
                    extract={"schema": SPACE_DETAIL_SCHEMA},
                )
                extracted = result.get("extract", {}) if isinstance(result, dict) else {}

                if not extracted.get("name"):
                    continue

                # Check relevance based on extracted data
                if not self._is_relevant(url, extracted):
                    continue

                # Convert price: prefer monthly, estimate from daily/hourly if needed
                price = extracted.get("price_monthly")
                if not price and extracted.get("price_daily"):
                    price = extracted["price_daily"] * 22  # ~22 work days
                if not price and extracted.get("price_hourly"):
                    price = extracted["price_hourly"] * 8 * 22  # 8hr days, 22 days

                listing = StudioListing(
                    source=self.name,
                    source_url=url,
                    title=extracted.get("name", "Spacefinder Space"),
                    address=extracted.get("address"),
                    neighborhood=extracted.get("neighborhood"),
                    size_sqft=extracted.get("size_sqft"),
                    price_monthly=price,
                    photos=extracted.get("photos", []),
                    amenities=extracted.get("amenities", []),
                    description=extracted.get("description"),
                    use_type=", ".join(extracted.get("space_types", ["studio"])),
                )
                slug = extracted["name"].replace(" ", "-").lower()[:50]
                listing.id = f"{self.name}-{slug}"
                listing.source_id = slug
                listings.append(listing)

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")

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
