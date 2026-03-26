from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Borough(str, Enum):
    MANHATTAN = "manhattan"
    BROOKLYN = "brooklyn"
    QUEENS = "queens"
    BRONX = "bronx"
    STATEN_ISLAND = "staten_island"


class LeaseTerms(BaseModel):
    min_months: Optional[int] = Field(None, description="Minimum lease duration in months")
    max_months: Optional[int] = Field(None, description="Maximum lease duration in months")
    available_date: Optional[str] = Field(None, description="ISO date when space becomes available")
    shared_ok: Optional[bool] = Field(None, description="Whether co-tenants are allowed")


class StudioListing(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier (source-sourceId)")
    source: str = Field(description="Source site identifier, e.g. 'rockella', 'chashama'")
    source_url: str = Field(description="Original listing URL")
    source_id: Optional[str] = Field(None, description="ID from the source site if available")
    title: str = Field(description="Listing title or studio name")
    address: Optional[str] = Field(None, description="Full street address")
    neighborhood: Optional[str] = Field(None, description="NYC neighborhood name")
    borough: Optional[Borough] = Field(None, description="NYC borough")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    size_sqft: Optional[int] = Field(None, description="Size in square feet")
    price_monthly: Optional[float] = Field(None, description="Monthly rent in USD")
    photos: list[str] = Field(default_factory=list, description="URLs of listing photos")
    amenities: list[str] = Field(default_factory=list, description="List of amenities")
    description: Optional[str] = Field(None, description="Listing description text")
    lease_terms: Optional[LeaseTerms] = None
    use_type: Optional[str] = Field(None, description="e.g. studio, live-work, shared")
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of when this was scraped",
    )


class ScraperResult(BaseModel):
    source: str
    listings: list[StudioListing] = Field(default_factory=list)
    credits_used: int = 0
    errors: list[str] = Field(default_factory=list)


# Firecrawl extraction schema — derived from StudioListing for use with
# Firecrawl's structured JSON extraction. We define it separately because
# Firecrawl's extract format differs from Pydantic's full schema.
FIRECRAWL_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name or title of the studio space"},
                    "address": {"type": "string", "description": "Full street address"},
                    "neighborhood": {"type": "string", "description": "NYC neighborhood"},
                    "size_sqft": {"type": "integer", "description": "Size in square feet"},
                    "price_monthly": {"type": "number", "description": "Monthly rent in USD"},
                    "photos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Photo URLs",
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Amenities list",
                    },
                    "description": {"type": "string", "description": "Listing description"},
                    "use_type": {
                        "type": "string",
                        "description": "Type: studio, live-work, shared, rehearsal, etc.",
                    },
                    "url": {"type": "string", "description": "Link to the listing detail page"},
                },
            },
        }
    },
}
