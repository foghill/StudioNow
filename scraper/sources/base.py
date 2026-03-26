from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..client import FirecrawlClient
from ..config import Config
from ..models import ScraperResult

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all source scrapers."""

    name: str = ""
    domain: str = ""

    def __init__(self, client: FirecrawlClient, config: Config):
        self.client = client
        self.config = config

    @abstractmethod
    def scrape(self) -> ScraperResult:
        """Scrape listings from this source. Must be implemented by subclasses."""
        ...

    def check_robots(self, path: str = "/") -> bool:
        if not self.domain:
            return True
        return FirecrawlClient.check_robots_txt(self.domain, path)

    def run(self) -> ScraperResult:
        """Run the scraper with error handling."""
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
            return ScraperResult(
                source=self.name,
                credits_used=0,
                errors=[f"Fatal: {e}"],
            )
