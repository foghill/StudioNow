from __future__ import annotations

import logging

from ..client import FirecrawlClient
from ..config import Config
from ..models import FIRECRAWL_EXTRACT_SCHEMA, ScraperResult, StudioListing

logger = logging.getLogger(__name__)

# Rockella Space pages to scrape — each borough has its own page
PAGES = [
    "https://rockella.space/",
    "https://rockella.space/brooklyn",
    "https://rockella.space/queens",
    "https://rockella.space/manhattan",
]


class RockellaScraper:
    name = "rockella"
    domain = "rockella.space"

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    def scrape(self) -> ScraperResult:
        if not FirecrawlClient.check_robots_txt(self.domain):
            return ScraperResult(
                source=self.name,
                errors=["robots.txt disallows scraping"],
            )

        all_listings: list[StudioListing] = []
        errors: list[str] = []
        credits = 0

        for url in PAGES:
            try:
                result = self.client.scrape(
                    url,
                    extract={"schema": FIRECRAWL_EXTRACT_SCHEMA},
                )
                credits += 1
                extracted = result.get("extract", {}) if isinstance(result, dict) else {}
                raw_listings = extracted if isinstance(extracted, list) else extracted.get("listings", [])

                for raw in raw_listings:
                    listing = StudioListing(
                        source=self.name,
                        source_url=raw.get("url", url),
                        source_id=raw.get("title", "").replace(" ", "-").lower(),
                        title=raw.get("title", "Unknown Studio"),
                        address=raw.get("address"),
                        neighborhood=raw.get("neighborhood"),
                        size_sqft=raw.get("size_sqft"),
                        price_monthly=raw.get("price_monthly"),
                        photos=raw.get("photos", []),
                        amenities=raw.get("amenities", []),
                        description=raw.get("description"),
                        use_type=raw.get("use_type", "studio"),
                    )
                    listing.id = f"{self.name}-{listing.source_id}"
                    all_listings.append(listing)

                logger.info("Rockella %s: found %d listings", url, len(raw_listings))

            except Exception as e:
                errors.append(f"Error scraping {url}: {e}")
                logger.error("Rockella error on %s: %s", url, e)

        # Deduplicate by title
        seen = set()
        unique = []
        for listing in all_listings:
            key = listing.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(listing)

        return ScraperResult(
            source=self.name,
            listings=unique,
            credits_used=credits,
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
