from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class SourceConfig:
    name: str
    enabled: bool = True
    restricted: bool = False  # True = disabled unless --include-restricted
    priority: str = "medium"  # high, medium, low


# Source registry — order determines default execution order
SOURCES: list[SourceConfig] = [
    SourceConfig(name="rockella", priority="high"),
    SourceConfig(name="chashama", priority="high"),
    SourceConfig(name="spacefinder", priority="high"),
    SourceConfig(name="loopnet", priority="medium"),
    SourceConfig(name="nyfa", priority="medium"),
    SourceConfig(name="listings_project", priority="medium"),
    SourceConfig(name="craigslist", restricted=True, priority="medium"),
    SourceConfig(name="streeteasy", restricted=True, priority="low"),
    # Group A — API-based (no Firecrawl credits)
    SourceConfig(name="nyc_opendata", priority="high"),
    SourceConfig(name="coworker", priority="high"),
    # Group B — New Firecrawl scrapers (artist-specific sites)
    SourceConfig(name="ny_studio_factory", priority="medium"),
    SourceConfig(name="navy_yard", priority="medium"),
    SourceConfig(name="gmdc", priority="medium"),
    SourceConfig(name="mana_contemporary", priority="medium"),
    SourceConfig(name="pioneer_works", priority="medium"),
    SourceConfig(name="industry_city", priority="medium"),
]


@dataclass
class Config:
    api_key: str = field(default_factory=lambda: os.environ.get("FIRECRAWL_API_KEY", ""))
    credit_limit: int = 500
    rate_limit_delay: float = 2.0  # seconds between requests
    max_retries: int = 3
    request_timeout: int = 60  # seconds
    data_dir: str = field(
        default_factory=lambda: os.environ.get("DATA_DIR") or os.path.join(os.path.dirname(__file__), "data")
    )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY not set. "
                "Sign up at https://firecrawl.dev and set the env var:\n"
                "  export FIRECRAWL_API_KEY=fc-your-key-here\n"
                "Or add it to a .env file in the project root."
            )

    def get_sources(
        self, priority: str | None = None, include_restricted: bool = False
    ) -> list[SourceConfig]:
        results = []
        for s in SOURCES:
            if s.restricted and not include_restricted:
                continue
            if priority and s.priority != priority:
                continue
            if s.enabled:
                results.append(s)
        return results
