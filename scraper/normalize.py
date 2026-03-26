from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone

from .config import Config
from .models import Borough, StudioListing

logger = logging.getLogger(__name__)

# NYC neighborhood to borough mapping
NEIGHBORHOOD_BOROUGH: dict[str, Borough] = {
    # Brooklyn
    "bushwick": Borough.BROOKLYN,
    "williamsburg": Borough.BROOKLYN,
    "greenpoint": Borough.BROOKLYN,
    "bed-stuy": Borough.BROOKLYN,
    "bedford-stuyvesant": Borough.BROOKLYN,
    "gowanus": Borough.BROOKLYN,
    "park slope": Borough.BROOKLYN,
    "red hook": Borough.BROOKLYN,
    "dumbo": Borough.BROOKLYN,
    "downtown brooklyn": Borough.BROOKLYN,
    "sunset park": Borough.BROOKLYN,
    "east new york": Borough.BROOKLYN,
    "flatbush": Borough.BROOKLYN,
    "crown heights": Borough.BROOKLYN,
    "prospect heights": Borough.BROOKLYN,
    "cobble hill": Borough.BROOKLYN,
    "carroll gardens": Borough.BROOKLYN,
    "boerum hill": Borough.BROOKLYN,
    "fort greene": Borough.BROOKLYN,
    "clinton hill": Borough.BROOKLYN,
    "prospect lefferts gardens": Borough.BROOKLYN,
    "bay ridge": Borough.BROOKLYN,
    "bensonhurst": Borough.BROOKLYN,
    "borough park": Borough.BROOKLYN,
    "brownsville": Borough.BROOKLYN,
    "east williamsburg": Borough.BROOKLYN,
    "industry city": Borough.BROOKLYN,
    "brooklyn navy yard": Borough.BROOKLYN,
    "brooklyn army terminal": Borough.BROOKLYN,
    # Manhattan
    "chelsea": Borough.MANHATTAN,
    "soho": Borough.MANHATTAN,
    "noho": Borough.MANHATTAN,
    "tribeca": Borough.MANHATTAN,
    "lower east side": Borough.MANHATTAN,
    "les": Borough.MANHATTAN,
    "east village": Borough.MANHATTAN,
    "west village": Borough.MANHATTAN,
    "greenwich village": Borough.MANHATTAN,
    "midtown": Borough.MANHATTAN,
    "nomad": Borough.MANHATTAN,
    "flatiron": Borough.MANHATTAN,
    "gramercy": Borough.MANHATTAN,
    "murray hill": Borough.MANHATTAN,
    "hells kitchen": Borough.MANHATTAN,
    "hell's kitchen": Borough.MANHATTAN,
    "upper west side": Borough.MANHATTAN,
    "upper east side": Borough.MANHATTAN,
    "harlem": Borough.MANHATTAN,
    "east harlem": Borough.MANHATTAN,
    "washington heights": Borough.MANHATTAN,
    "inwood": Borough.MANHATTAN,
    "financial district": Borough.MANHATTAN,
    "fidi": Borough.MANHATTAN,
    "chinatown": Borough.MANHATTAN,
    "little italy": Borough.MANHATTAN,
    "nolita": Borough.MANHATTAN,
    "meatpacking": Borough.MANHATTAN,
    "meatpacking district": Borough.MANHATTAN,
    "two bridges": Borough.MANHATTAN,
    # Queens
    "long island city": Borough.QUEENS,
    "lic": Borough.QUEENS,
    "astoria": Borough.QUEENS,
    "ridgewood": Borough.QUEENS,
    "sunnyside": Borough.QUEENS,
    "woodside": Borough.QUEENS,
    "jackson heights": Borough.QUEENS,
    "flushing": Borough.QUEENS,
    "jamaica": Borough.QUEENS,
    "forest hills": Borough.QUEENS,
    "rego park": Borough.QUEENS,
    "maspeth": Borough.QUEENS,
    "glendale": Borough.QUEENS,
    "rockaway": Borough.QUEENS,
    "far rockaway": Borough.QUEENS,
    # Bronx
    "south bronx": Borough.BRONX,
    "mott haven": Borough.BRONX,
    "hunts point": Borough.BRONX,
    "fordham": Borough.BRONX,
    "kingsbridge": Borough.BRONX,
    "riverdale": Borough.BRONX,
    "concourse": Borough.BRONX,
    "port morris": Borough.BRONX,
    # Staten Island
    "st. george": Borough.STATEN_ISLAND,
    "stapleton": Borough.STATEN_ISLAND,
    "snug harbor": Borough.STATEN_ISLAND,
}

# Borough keywords found in addresses
BOROUGH_KEYWORDS = {
    "brooklyn": Borough.BROOKLYN,
    "manhattan": Borough.MANHATTAN,
    "queens": Borough.QUEENS,
    "bronx": Borough.BRONX,
    "staten island": Borough.STATEN_ISLAND,
    "new york, ny": Borough.MANHATTAN,  # default assumption
}


def _normalize_price(price: float | str | None) -> float | None:
    """Convert price strings or non-monthly rates to monthly USD float."""
    if price is None:
        return None
    if isinstance(price, str):
        cleaned = re.sub(r"[^\d.]", "", price)
        if not cleaned:
            return None
        price = float(cleaned)
    if isinstance(price, (int, float)):
        return round(float(price), 2)
    return None


def _normalize_sqft(size: int | str | None) -> int | None:
    """Parse size strings into integer sqft."""
    if size is None:
        return None
    if isinstance(size, int):
        return size
    if isinstance(size, str):
        cleaned = re.sub(r"[^\d]", "", size)
        return int(cleaned) if cleaned else None
    return None


def _infer_borough(listing: StudioListing) -> Borough | None:
    """Try to infer borough from neighborhood or address."""
    # Check neighborhood
    if listing.neighborhood:
        key = listing.neighborhood.lower().strip()
        if key in NEIGHBORHOOD_BOROUGH:
            return NEIGHBORHOOD_BOROUGH[key]

    # Check address for borough keywords
    if listing.address:
        addr_lower = listing.address.lower()
        for keyword, borough in BOROUGH_KEYWORDS.items():
            if keyword in addr_lower:
                return borough

    return None


def _listing_hash(listing: StudioListing) -> str:
    """Generate a deduplication hash based on normalized address + size."""
    addr = (listing.address or "").lower().strip()
    addr = re.sub(r"\s+", " ", addr)
    size = listing.size_sqft or 0
    return hashlib.md5(f"{addr}|{size}".encode()).hexdigest()


def normalize_listings(
    listings: list[StudioListing],
) -> tuple[list[StudioListing], list[dict]]:
    """
    Normalize and deduplicate listings.
    Returns (valid_listings, rejected_entries).
    """
    normalized: list[StudioListing] = []
    rejected: list[dict] = []
    seen_hashes: dict[str, StudioListing] = {}

    for listing in listings:
        # Normalize price
        listing.price_monthly = _normalize_price(listing.price_monthly)

        # Normalize size
        listing.size_sqft = _normalize_sqft(listing.size_sqft)

        # Infer borough if missing
        if not listing.borough:
            listing.borough = _infer_borough(listing)

        # Validate: must have at least address or title, and some useful data
        if not listing.address and not listing.title:
            rejected.append({
                "listing": listing.model_dump(),
                "reason": "Missing both address and title",
            })
            continue

        # Generate ID if missing
        if not listing.id:
            slug = (listing.title or "unknown").replace(" ", "-").lower()[:50]
            listing.id = f"{listing.source}-{slug}"

        # Deduplicate
        h = _listing_hash(listing)
        if h in seen_hashes:
            existing = seen_hashes[h]
            # Merge: keep the one with more data, combine photos
            existing_fields = sum(1 for v in existing.model_dump().values() if v)
            new_fields = sum(1 for v in listing.model_dump().values() if v)
            if new_fields > existing_fields:
                # New one has more data — replace but merge photos
                listing.photos = list(set(listing.photos + existing.photos))
                seen_hashes[h] = listing
            else:
                # Existing has more data — just merge photos
                existing.photos = list(set(existing.photos + listing.photos))
            continue

        seen_hashes[h] = listing

    normalized = list(seen_hashes.values())
    logger.info(
        "Normalization: %d input -> %d valid, %d rejected, %d deduped",
        len(listings),
        len(normalized),
        len(rejected),
        len(listings) - len(normalized) - len(rejected),
    )
    return normalized, rejected


def save_results(
    listings: list[StudioListing],
    rejected: list[dict],
    config: Config,
) -> str:
    """Save normalized listings to JSON. Returns the output file path."""
    output_dir = os.path.join(config.data_dir, "normalized")
    os.makedirs(output_dir, exist_ok=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_listings": len(listings),
        "listings": [l.model_dump(mode="json") for l in listings],
    }

    output_path = os.path.join(output_dir, "listings.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Saved %d listings to %s", len(listings), output_path)

    # Save rejected listings for review
    if rejected:
        rejected_path = os.path.join(output_dir, "rejected.json")
        with open(rejected_path, "w") as f:
            json.dump(rejected, f, indent=2, default=str)
        logger.info("Saved %d rejected entries to %s", len(rejected), rejected_path)

    return output_path


def save_raw(source: str, data: dict | list, config: Config) -> str:
    """Save raw scraper output for debugging."""
    raw_dir = os.path.join(config.data_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(raw_dir, f"{source}_{timestamp}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Saved raw data to %s", path)
    return path
