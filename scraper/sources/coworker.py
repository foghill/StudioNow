"""
Coworker.com — Free coworking space API.

Uses the Coworker public API to find creative/artist coworking spaces in NYC.
No Firecrawl credits needed.

API: https://www.coworker.com/coworker-api
"""
from __future__ import annotations

import logging

import httpx

from ..config import Config
from ..models import ScraperResult, StudioListing

logger = logging.getLogger(__name__)

# Coworker search endpoint — we search for creative/art spaces in NYC
SEARCH_URL = "https://www.coworker.com/api/v1/spaces"

# Keywords to filter for creative/artist relevant spaces
CREATIVE_KEYWORDS = [
    "studio", "art", "artist", "creative", "maker", "design",
    "workshop", "gallery", "craft", "photo", "music", "media",
]


class CoworkerScraper:
    name = "coworker"
    domain = "www.coworker.com"

    def __init__(self, client=None, config: Config | None = None):
        self.config = config or Config()

    def _search_spaces(self, city: str = "New York") -> list[dict]:
        """Query Coworker API for spaces in a city."""
        try:
            resp = httpx.get(
                SEARCH_URL,
                params={"city": city, "country": "US", "limit": 100},
                timeout=30,
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("data", data.get("spaces", []))
            else:
                logger.warning("Coworker API returned %d", resp.status_code)
                return []
        except Exception as e:
            logger.error("Coworker API error: %s", e)
            return []

    def _is_creative(self, space: dict) -> bool:
        """Check if a coworking space is relevant to creative/artist use."""
        searchable = " ".join([
            space.get("name", ""),
            space.get("description", ""),
            " ".join(space.get("amenities", [])) if isinstance(space.get("amenities"), list) else "",
            space.get("type", ""),
        ]).lower()
        return any(kw in searchable for kw in CREATIVE_KEYWORDS)

    def scrape(self) -> ScraperResult:
        errors: list[str] = []
        listings: list[StudioListing] = []

        spaces = self._search_spaces("New York")
        if not spaces:
            # Fallback: try scraping the Coworker NYC listing page with Firecrawl
            errors.append("Coworker API returned no results — API may require auth or have changed")
            return ScraperResult(source=self.name, errors=errors)

        logger.info("Coworker: received %d spaces, filtering for creative/artist relevance", len(spaces))

        for space in spaces:
            if not self._is_creative(space):
                continue

            name = space.get("name", "Coworking Space")
            address = space.get("address") or space.get("full_address")

            # Parse price
            price = None
            if space.get("price"):
                try:
                    price = float(str(space["price"]).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Photos
            photos = []
            if space.get("image"):
                photos.append(space["image"])
            if space.get("images") and isinstance(space["images"], list):
                photos.extend(space["images"][:5])

            # Amenities
            amenities = space.get("amenities", [])
            if isinstance(amenities, str):
                amenities = [a.strip() for a in amenities.split(",")]

            listing = StudioListing(
                source=self.name,
                source_url=space.get("url", f"https://www.coworker.com/search/new-york"),
                title=name,
                address=address,
                neighborhood=space.get("neighborhood") or space.get("area"),
                latitude=space.get("latitude") or space.get("lat"),
                longitude=space.get("longitude") or space.get("lng"),
                price_monthly=price,
                photos=photos,
                amenities=amenities if isinstance(amenities, list) else [],
                description=space.get("description"),
                use_type="coworking",
            )
            slug = name.replace(" ", "-").lower()[:50]
            listing.id = f"{self.name}-{slug}"
            listing.source_id = slug
            listings.append(listing)

        return ScraperResult(
            source=self.name,
            listings=listings,
            credits_used=0,
            errors=errors,
        )

    def run(self) -> ScraperResult:
        logger.info("Starting scraper: %s (API-based, no Firecrawl credits)", self.name)
        try:
            result = self.scrape()
            logger.info(
                "%s: collected %d listings, %d errors",
                self.name,
                len(result.listings),
                len(result.errors),
            )
            return result
        except Exception as e:
            logger.error("%s: fatal error: %s", self.name, e)
            return ScraperResult(source=self.name, errors=[f"Fatal: {e}"])
