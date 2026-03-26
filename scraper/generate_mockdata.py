#!/usr/bin/env python3
"""Convert scraper/data/normalized/listings.json → StudioNow/Data/MockData.swift listings array."""

from __future__ import annotations

import json
import math
import os
import random

# ── Coordinate defaults by neighborhood/borough (lat, lon) ─────────────────
NEIGHBORHOOD_COORDS: dict[str, tuple[float, float]] = {
    "Brooklyn": (40.6579, -73.9052),     # E New York Ave area
    "Queens":   (40.7037, -73.9131),     # Ridgewood / Centre St area
    "Manhattan": (40.7527, -73.9967),    # Midtown / 8th Ave area
    "Bushwick":  (40.7054, -73.9217),
    "Williamsburg": (40.7140, -73.9642),
    "Long Island City": (40.7440, -73.9484),
    "Gowanus":   (40.6745, -73.9893),
    "Bed-Stuy":  (40.6831, -73.9338),
    "Crown Heights": (40.6712, -73.9526),
    "Harlem":    (40.8118, -73.9488),
    "Astoria":   (40.7554, -73.9302),
    "Greenpoint": (40.7299, -73.9543),
    "Red Hook":  (40.6761, -74.0094),
    "Mott Haven": (40.8082, -73.9257),
    "Sunset Park": (40.6502, -74.0031),
    "East New York": (40.6690, -73.8850),
    "South Bronx": (40.8168, -73.9164),
    "Jamaica":   (40.7019, -73.7963),
    "Ridgewood": (40.7040, -73.9129),
    "Sunnyside": (40.7437, -73.9196),
    "Flatbush":  (40.6409, -73.9615),
    "Inwood":    (40.8676, -73.9227),
    "Washington Heights": (40.8467, -73.9394),
}

# Amenities inferred per building when scraper returns empty list
BUILDING_AMENITIES: dict[str, list[str]] = {
    "1660 E New York Ave": ["24/7 Access", "Natural Light", "Shared Bathrooms"],
    "1639 Centre St": ["24/7 Access", "Natural Light", "Shared Bathrooms"],
}

SWIFT_HEADER = '''\
import Foundation

enum MockData {
    static let listings: [StudioListing] = {
        let calendar = Calendar.current
        let now = Date()

        func futureDate(daysFromNow: Int) -> Date {
            calendar.date(byAdding: .day, value: daysFromNow, to: now) ?? now
        }

        return [
'''

SWIFT_FOOTER = '''\
        ]
    }()

'''


def escape_swift_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def swift_string_list(items: list[str]) -> str:
    if not items:
        return "[]"
    escaped = [f'"{escape_swift_string(i)}"' for i in items]
    return "[" + ", ".join(escaped) + "]"


def coord_for(listing: dict) -> tuple[float, float]:
    lat, lon = listing.get("latitude"), listing.get("longitude")
    if lat and lon:
        return float(lat), float(lon)
    neighborhood = listing.get("neighborhood") or ""
    borough = listing.get("borough") or ""
    key = neighborhood or borough.title()
    if key in NEIGHBORHOOD_COORDS:
        return NEIGHBORHOOD_COORDS[key]
    return 40.7282, -73.9542  # NYC centre


def amenities_for(listing: dict) -> list[str]:
    amenities = listing.get("amenities") or []
    if amenities:
        return amenities
    addr = listing.get("address") or ""
    for building, defaults in BUILDING_AMENITIES.items():
        if building in addr:
            return defaults
    return []


def address_for(listing: dict) -> str:
    title = listing.get("title") or ""
    addr = listing.get("address") or ""
    if addr and addr.lower() not in ("manhattan", "brooklyn", "queens", "the bronx"):
        return f"{title} · {addr}"
    # address is just borough name; use the source URL to hint location
    return title


def generate_listings(listings: list[dict]) -> str:
    lines = []
    random.seed(42)
    days_pool = list(range(5, 75))
    random.shuffle(days_pool)
    scores = [None, None, 0.55, 0.62, 0.68, 0.74, 0.79, 0.85, 0.91, None, 0.60, 0.72]

    for i, l in enumerate(listings):
        days = days_pool[i % len(days_pool)]
        score = scores[i % len(scores)]
        lat, lon = coord_for(l)
        amenities = amenities_for(l)
        address = address_for(l)
        neighborhood = l.get("neighborhood") or "New York"
        sqft = l.get("size_sqft") or 200
        rent = int(l.get("price_monthly") or 0)
        photos = l.get("photos") or []
        lease_months = 12
        if l.get("lease_terms") and l["lease_terms"].get("min_months"):
            lease_months = int(l["lease_terms"]["min_months"])

        if score is None:
            score_str = "nil"
        else:
            score_str = str(score)

        lines.append(f'            StudioListing(')
        lines.append(f'                id: UUID(),')
        lines.append(f'                address: "{escape_swift_string(address)}",')
        lines.append(f'                neighborhood: "{escape_swift_string(neighborhood)}",')
        lines.append(f'                sqft: {sqft},')
        lines.append(f'                monthlyRent: {rent},')
        lines.append(f'                photos: {swift_string_list(photos)},')
        lines.append(f'                amenities: {swift_string_list(amenities)},')
        lines.append(f'                leaseTermMonths: {lease_months},')
        lines.append(f'                availableDate: futureDate(daysFromNow: {days}),')
        lines.append(f'                coTenantCompatibilityScore: {score_str},')
        lines.append(f'                latitude: {lat},')
        lines.append(f'                longitude: {lon}')
        lines.append(f'            ),')

    # Remove trailing comma from last entry
    if lines and lines[-1] == '            ),':
        lines[-1] = '            )'

    return "\n".join(lines)


NEIGHBORHOODS_SWIFT = '''\
    static let neighborhoods: [String] = [
        "Astoria",
        "Bed-Stuy",
        "Brooklyn",
        "Bushwick",
        "Crown Heights",
        "East New York",
        "Flatbush",
        "Gowanus",
        "Greenpoint",
        "Harlem",
        "Inwood",
        "Jamaica",
        "Long Island City",
        "Manhattan",
        "Mott Haven",
        "Queens",
        "Red Hook",
        "Ridgewood",
        "South Bronx",
        "Sunnyside",
        "Sunset Park",
        "The Bronx",
        "Washington Heights",
        "Williamsburg"
    ]

    /// Borough-level entries and their constituent neighborhoods — used for broad filtering.
    static let boroughNeighborhoods: [String: [String]] = [
        "Brooklyn": ["Bushwick", "Williamsburg", "Gowanus", "Bed-Stuy", "Crown Heights",
                     "Greenpoint", "Red Hook", "Sunset Park", "East New York", "Flatbush",
                     "Dumbo", "Park Slope", "Carroll Gardens", "Cobble Hill", "Fort Greene"],
        "Manhattan": ["Harlem", "Inwood", "Washington Heights", "East Harlem", "SoHo",
                      "Chelsea", "Lower East Side", "East Village", "West Village", "Midtown", "Tribeca"],
        "Queens": ["Long Island City", "Astoria", "Jamaica", "Ridgewood", "Sunnyside",
                   "Flushing", "Jackson Heights"],
        "The Bronx": ["South Bronx", "Mott Haven", "Hunts Point", "Port Morris"],
    ]
'''

DISCIPLINES_SWIFT = '''\
    static let disciplines: [String] = [
        "Painting",
        "Sculpture",
        "Photography",
        "Printmaking",
        "Ceramics",
        "Textile / Fiber Arts",
        "Installation Art",
        "Video / Film",
        "Performance Art",
        "Drawing",
        "Mixed Media",
        "Illustration",
        "Muralism",
        "Woodworking",
        "Metalworking",
        "Glassblowing",
        "Digital Art",
        "Sound Art",
        "Collage",
        "Other"
    ]
'''

MEDIATION_SWIFT = '''\
    static let mediationSessions: [MediationSession] = {
        let calendar = Calendar.current
        let now = Date()
        return [
            MediationSession(
                id: UUID(),
                date: calendar.date(byAdding: .day, value: 5, to: now) ?? now,
                topic: "Studio hours and noise boundaries",
                status: "Scheduled"
            ),
            MediationSession(
                id: UUID(),
                date: calendar.date(byAdding: .day, value: 18, to: now) ?? now,
                topic: "Shared supply storage arrangement",
                status: "Pending Confirmation"
            )
        ]
    }()
}
'''


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "data", "normalized", "listings.json")
    output_path = os.path.join(
        script_dir, "..", "StudioNow", "Data", "MockData.swift"
    )

    with open(json_path) as f:
        data = json.load(f)

    listings = data.get("listings", [])
    print(f"Loaded {len(listings)} listings from {json_path}")

    listing_body = generate_listings(listings)

    swift = (
        SWIFT_HEADER
        + listing_body
        + "\n"
        + SWIFT_FOOTER
        + NEIGHBORHOODS_SWIFT
        + "\n"
        + DISCIPLINES_SWIFT
        + "\n"
        + MEDIATION_SWIFT
    )

    with open(output_path, "w") as f:
        f.write(swift)

    print(f"Written {len(listings)} listings → {output_path}")


if __name__ == "__main__":
    main()
