from __future__ import annotations

import logging
import time

import httpx
from firecrawl import Firecrawl as FirecrawlApp

from .config import Config

logger = logging.getLogger(__name__)


class CreditExhaustedError(Exception):
    pass


class FirecrawlClient:
    """Wrapper around the Firecrawl SDK with credit tracking, rate limiting, and retries."""

    def __init__(self, config: Config):
        config.validate()
        self.app = FirecrawlApp(api_key=config.api_key)
        self.config = config
        self.credits_used = 0
        self._last_request_time = 0.0

    def _check_budget(self, cost: int = 1) -> None:
        if self.credits_used + cost > self.config.credit_limit:
            raise CreditExhaustedError(
                f"Credit limit reached ({self.credits_used}/{self.config.credit_limit}). "
                f"Requested {cost} more credits."
            )
        if self.credits_used >= self.config.credit_limit * 0.8:
            logger.warning(
                "Credit usage at %d/%d (%.0f%%)",
                self.credits_used,
                self.config.credit_limit,
                self.credits_used / self.config.credit_limit * 100,
            )

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _retry(self, fn, retries: int | None = None):
        retries = retries or self.config.max_retries
        last_error = None
        for attempt in range(retries):
            try:
                self._rate_limit()
                return fn()
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                retryable = any(
                    code in err_str for code in ["429", "500", "502", "503", "timeout"]
                )
                if not retryable or attempt == retries - 1:
                    raise
                wait = (2**attempt) * 5
                logger.warning(
                    "Retryable error (attempt %d/%d), waiting %ds: %s",
                    attempt + 1,
                    retries,
                    wait,
                    e,
                )
                time.sleep(wait)
        raise last_error  # type: ignore[misc]

    def scrape(self, url: str, **kwargs) -> dict:
        self._check_budget(1)
        logger.info("Scraping: %s", url)
        # Use extract for structured data extraction (supports both extract= and json= conventions)
        extract_opts = kwargs.pop("extract", None) or kwargs.pop("json", None)
        if extract_opts:
            schema = extract_opts.get("schema")
            prompt = extract_opts.get("prompt") or "Extract all relevant listing data from this page according to the schema."
            # Strip formats=["extract"] since we're using the dedicated extract endpoint
            kwargs.pop("formats", None)
            result = self._retry(lambda: self.app.extract([url], schema=schema, prompt=prompt, **kwargs))
            self.credits_used += 1
            logger.info("Extract complete (%d credits used)", self.credits_used)
            # Extract returns ExtractResponse with data as list of dicts
            if hasattr(result, "model_dump"):
                data = result.model_dump()
                if data.get("success") and data.get("data"):
                    # For single URL, data is list with one item
                    extracted = data["data"][0] if isinstance(data["data"], list) and data["data"] else data["data"]
                    return {"extract": extracted}
            return {"extract": {}}
        else:
            # Fallback to scrape
            result = self._retry(lambda: self.app.scrape(url, **kwargs))
            self.credits_used += 1
            logger.info("Scrape complete (%d credits used)", self.credits_used)
            # SDK returns a Document object; normalize to dict for scraper compatibility
            if hasattr(result, "model_dump"):
                data = result.model_dump()
                # Remap "json" key back to "extract" so existing scrapers work unchanged
                if "json" in data and "extract" not in data:
                    data["extract"] = data["json"]
                return data
            return result

    def crawl(self, url: str, **kwargs) -> dict:
        limit = kwargs.get("limit", 10)
        self._check_budget(limit)
        logger.info("Crawling: %s (limit=%d)", url, limit)
        result = self._retry(lambda: self.app.crawl(url, **kwargs))
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        pages = len(result.get("data", [])) if isinstance(result, dict) else 0
        self.credits_used += max(pages, 1)
        logger.info("Crawl complete: %d pages (%d credits used)", pages, self.credits_used)
        return result

    def map_url(self, url: str, **kwargs) -> list[str]:
        self._check_budget(1)
        logger.info("Mapping: %s", url)
        result = self._retry(lambda: self.app.map(url, **kwargs))
        self.credits_used += 1
        # SDK v4 returns MapData object with .links; normalize to list
        if hasattr(result, "links"):
            urls = result.links or []
        elif isinstance(result, list):
            urls = result
        else:
            urls = result.get("links", [])
        logger.info("Map complete: %d URLs found (%d credits used)", len(urls), self.credits_used)
        return urls

    def search(self, query: str, **kwargs) -> dict:
        self._check_budget(1)
        logger.info("Searching: %s", query)
        result = self._retry(lambda: self.app.search(query, params=kwargs))
        self.credits_used += 1
        return result

    @staticmethod
    def check_robots_txt(domain: str, path: str = "/") -> bool:
        """Check if scraping a path is allowed by robots.txt. Returns True if allowed."""
        try:
            resp = httpx.get(f"https://{domain}/robots.txt", timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                return True  # No robots.txt = allowed
            # Simple check: look for Disallow lines matching our path
            for line in resp.text.splitlines():
                line = line.strip().lower()
                if line.startswith("disallow:"):
                    disallowed = line.split(":", 1)[1].strip()
                    if disallowed and path.startswith(disallowed):
                        logger.warning("robots.txt disallows %s on %s", path, domain)
                        return False
            return True
        except Exception as e:
            logger.warning("Could not fetch robots.txt for %s: %s", domain, e)
            return True  # Assume allowed on error
