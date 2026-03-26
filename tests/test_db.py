"""
Tests for the SQLite database layer (scraper/db.py).

Covers:
  - Schema initialization
  - CRUD: insert, update (upsert), get by ID
  - Filtered queries: borough, neighborhood, price, sqft, source
  - Full-text search (FTS5)
  - Geo/nearby queries (R-tree)
  - Stale listing detection
  - Scrape run audit trail
  - JSON migration
  - Pagination
  - Stats

Usage:
    pytest tests/test_db.py -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile

import pytest

# Ensure project root is on path
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scraper.db import (
    finish_scrape_run,
    get_connection,
    get_listing_by_id,
    get_stats,
    import_from_json,
    init_db,
    mark_stale,
    query_listings,
    query_nearby,
    start_scrape_run,
    upsert_listing,
    upsert_listings,
)
from scraper.models import Borough, LeaseTerms, StudioListing


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_conn():
    """Create a fresh in-memory database for each test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_listings() -> list[StudioListing]:
    """A set of diverse test listings covering multiple boroughs, prices, sizes."""
    return [
        StudioListing(
            id="rockella-101",
            source="rockella",
            source_url="https://rockella.space/101",
            title="Studio 101",
            address="1660 E New York Ave, Brooklyn, NY 11212",
            neighborhood="Brownsville",
            borough=Borough.BROOKLYN,
            latitude=40.6628,
            longitude=-73.9108,
            size_sqft=170,
            price_monthly=850.0,
            photos=["https://example.com/101.jpg"],
            amenities=["WiFi", "24hr access"],
            description="Cozy artist studio in Brooklyn",
            use_type="studio",
        ),
        StudioListing(
            id="rockella-2411",
            source="rockella",
            source_url="https://rockella.space/2411",
            title="Studio 2411",
            address="520 8th Ave, New York, NY 10018",
            neighborhood="Midtown",
            borough=Borough.MANHATTAN,
            latitude=40.7527,
            longitude=-73.9935,
            size_sqft=171,
            price_monthly=1950.0,
            photos=["https://example.com/2411.jpg"],
            amenities=["WiFi", "HVAC", "freight elevator"],
            description="Midtown Manhattan studio with great amenities",
            use_type="studio",
        ),
        StudioListing(
            id="rockella-110",
            source="rockella",
            source_url="https://rockella.space/110",
            title="Studio 110",
            address="1639 Centre St, Queens, NY 11385",
            neighborhood="Ridgewood",
            borough=Borough.QUEENS,
            latitude=40.7004,
            longitude=-73.9068,
            size_sqft=303,
            price_monthly=1600.0,
            photos=[],
            amenities=["WiFi"],
            description="Spacious Queens studio",
            use_type="studio",
        ),
        StudioListing(
            id="opendata-arts-org-1",
            source="nyc_opendata",
            source_url="https://data.cityofnewyork.us",
            title="Brooklyn Ceramics Collective",
            address="45 Main St, Brooklyn, NY 11201",
            neighborhood="DUMBO",
            borough=Borough.BROOKLYN,
            latitude=40.7025,
            longitude=-73.9904,
            size_sqft=None,
            price_monthly=None,
            photos=[],
            amenities=["kiln", "wheel throwing"],
            description="Community ceramics workspace",
            use_type="cultural org",
        ),
        StudioListing(
            id="gmdc-greenpoint-1",
            source="gmdc",
            source_url="https://gmdconline.org/",
            title="GMDC Building 1",
            address="1155 Manhattan Ave, Brooklyn, NY 11222",
            neighborhood="Greenpoint",
            borough=Borough.BROOKLYN,
            size_sqft=500,
            price_monthly=1200.0,
            amenities=["freight elevator", "loading dock"],
            description="Woodworking and metal shop space",
            use_type="studio/workshop",
            lease_terms=LeaseTerms(min_months=12, shared_ok=True),
        ),
    ]


def _insert_samples(conn, listings):
    """Helper to insert sample listings."""
    upsert_listings(conn, listings)


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestSchema:
    def test_tables_created(self, db_conn):
        tables = {
            row[0]
            for row in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "listings" in tables
        assert "scrape_runs" in tables
        assert "listings_fts" in tables

    def test_indexes_created(self, db_conn):
        indexes = {
            row[0]
            for row in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_listings_borough" in indexes
        assert "idx_listings_price" in indexes
        assert "idx_listings_size" in indexes
        assert "idx_listings_source" in indexes
        assert "idx_listings_borough_price" in indexes

    def test_idempotent_init(self, db_conn):
        """Calling init_db twice should not error."""
        init_db(db_conn)
        init_db(db_conn)


# ── CRUD tests ────────────────────────────────────────────────────────────────

class TestCRUD:
    def test_insert_single(self, db_conn, sample_listings):
        listing = sample_listings[0]
        result = upsert_listing(db_conn, listing)
        db_conn.commit()
        assert result == "inserted"

        row = get_listing_by_id(db_conn, "rockella-101")
        assert row is not None
        assert row["title"] == "Studio 101"
        assert row["price_monthly"] == 850.0
        assert row["borough"] == "brooklyn"
        assert row["stale"] is False

    def test_upsert_updates_existing(self, db_conn, sample_listings):
        listing = sample_listings[0]
        upsert_listing(db_conn, listing)
        db_conn.commit()

        # Update the price
        listing.price_monthly = 900.0
        result = upsert_listing(db_conn, listing)
        db_conn.commit()
        assert result == "updated"

        row = get_listing_by_id(db_conn, "rockella-101")
        assert row["price_monthly"] == 900.0

    def test_upsert_refreshes_last_seen_at(self, db_conn, sample_listings):
        listing = sample_listings[0]
        upsert_listing(db_conn, listing)
        db_conn.commit()

        first_seen = db_conn.execute(
            "SELECT last_seen_at FROM listings WHERE id=?", (listing.id,)
        ).fetchone()[0]

        # Upsert again
        upsert_listing(db_conn, listing)
        db_conn.commit()

        second_seen = db_conn.execute(
            "SELECT last_seen_at FROM listings WHERE id=?", (listing.id,)
        ).fetchone()[0]

        assert second_seen >= first_seen

    def test_upsert_clears_stale_flag(self, db_conn, sample_listings):
        listing = sample_listings[0]
        upsert_listing(db_conn, listing)
        db_conn.commit()

        # Manually mark stale
        db_conn.execute("UPDATE listings SET stale=1 WHERE id=?", (listing.id,))
        db_conn.commit()

        # Re-upsert should clear stale
        upsert_listing(db_conn, listing)
        db_conn.commit()

        row = get_listing_by_id(db_conn, listing.id)
        assert row["stale"] is False

    def test_bulk_upsert(self, db_conn, sample_listings):
        counts = upsert_listings(db_conn, sample_listings)
        assert counts["inserted"] == 5
        assert counts["updated"] == 0

        # Upsert again — all updates
        counts = upsert_listings(db_conn, sample_listings)
        assert counts["inserted"] == 0
        assert counts["updated"] == 5

    def test_get_listing_by_id_not_found(self, db_conn):
        result = get_listing_by_id(db_conn, "nonexistent")
        assert result is None

    def test_photos_stored_as_json(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings[:1])
        row = get_listing_by_id(db_conn, "rockella-101")
        assert isinstance(row["photos"], list)
        assert row["photos"] == ["https://example.com/101.jpg"]

    def test_amenities_stored_as_json(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings[:1])
        row = get_listing_by_id(db_conn, "rockella-101")
        assert isinstance(row["amenities"], list)
        assert "WiFi" in row["amenities"]

    def test_lease_terms_stored_as_json(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        row = get_listing_by_id(db_conn, "gmdc-greenpoint-1")
        assert isinstance(row["lease_terms"], dict)
        assert row["lease_terms"]["shared_ok"] is True
        assert row["lease_terms"]["min_months"] == 12


# ── Filter tests ──────────────────────────────────────────────────────────────

class TestFilters:
    def test_filter_by_borough(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, borough="brooklyn")
        assert total == 3  # rockella-101, opendata, gmdc
        assert all(r["borough"] == "brooklyn" for r in results)

    def test_filter_by_neighborhood(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, neighborhood="midtown")
        assert total == 1
        assert results[0]["id"] == "rockella-2411"

    def test_filter_by_neighborhood_partial(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, neighborhood="green")
        assert total == 1  # Greenpoint
        assert results[0]["id"] == "gmdc-greenpoint-1"

    def test_filter_by_min_price(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, min_price=1500.0)
        assert total == 2  # 1950 and 1600
        prices = {r["price_monthly"] for r in results}
        assert prices == {1950.0, 1600.0}

    def test_filter_by_max_price(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, max_price=1000.0)
        assert total == 1  # 850
        assert results[0]["price_monthly"] == 850.0

    def test_filter_by_price_range(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, min_price=1000.0, max_price=1700.0)
        assert total == 2  # 1200 and 1600

    def test_filter_by_min_sqft(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, min_sqft=300)
        assert total == 2  # 303 and 500

    def test_filter_by_max_sqft(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, max_sqft=200)
        assert total == 2  # 170 and 171

    def test_filter_by_source(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, source="nyc_opendata")
        assert total == 1
        assert results[0]["id"] == "opendata-arts-org-1"

    def test_filter_excludes_stale_by_default(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        # Mark one listing stale
        db_conn.execute("UPDATE listings SET stale=1 WHERE id='rockella-101'")
        db_conn.commit()

        results, total = query_listings(db_conn)
        assert total == 4  # 5 - 1 stale

    def test_filter_include_stale(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        db_conn.execute("UPDATE listings SET stale=1 WHERE id='rockella-101'")
        db_conn.commit()

        results, total = query_listings(db_conn, include_stale=True)
        assert total == 5

    def test_combined_filters(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(
            db_conn, borough="brooklyn", min_price=1000.0, max_price=1500.0,
        )
        assert total == 1
        assert results[0]["id"] == "gmdc-greenpoint-1"

    def test_filter_shared_ok(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, shared_ok=True)
        assert total == 1
        assert results[0]["id"] == "gmdc-greenpoint-1"


# ── FTS tests ─────────────────────────────────────────────────────────────────

class TestFTS:
    def test_search_by_title(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="ceramics")
        assert total == 1
        assert results[0]["id"] == "opendata-arts-org-1"

    def test_search_by_description(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="woodworking")
        assert total == 1
        assert results[0]["id"] == "gmdc-greenpoint-1"

    def test_search_by_neighborhood(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="DUMBO")
        assert total == 1
        assert results[0]["id"] == "opendata-arts-org-1"

    def test_search_by_amenity(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="kiln")
        assert total == 1
        assert results[0]["id"] == "opendata-arts-org-1"

    def test_search_no_results(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="xyznonexistent")
        assert total == 0
        assert results == []

    def test_search_combined_with_filter(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, q="studio", borough="manhattan")
        assert total == 1
        assert results[0]["id"] == "rockella-2411"


# ── Geo tests ─────────────────────────────────────────────────────────────────

class TestGeo:
    def test_nearby_finds_close_listings(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        # Search near Brownsville, Brooklyn
        results = query_nearby(db_conn, lat=40.6628, lng=-73.9108, radius_km=2.0)
        assert len(results) >= 1
        ids = {r["id"] for r in results}
        assert "rockella-101" in ids

    def test_nearby_excludes_far_listings(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        # Search near Midtown Manhattan with small radius
        results = query_nearby(db_conn, lat=40.7527, lng=-73.9935, radius_km=1.0)
        ids = {r["id"] for r in results}
        assert "rockella-2411" in ids
        assert "rockella-101" not in ids  # Brownsville is far from Midtown

    def test_nearby_empty_results(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        # Search in the middle of the ocean
        results = query_nearby(db_conn, lat=0.0, lng=0.0, radius_km=1.0)
        assert len(results) == 0


# ── Stale detection tests ────────────────────────────────────────────────────

class TestStaleDetection:
    def test_mark_stale_works(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)

        # Backdate last_seen_at for all rockella listings to 8 days ago
        db_conn.execute("""
            UPDATE listings SET last_seen_at = datetime('now', '-8 days')
            WHERE source = 'rockella'
        """)
        db_conn.commit()

        # Only rockella-101 was "seen" this scrape
        staled = mark_stale(db_conn, "rockella", {"rockella-101"})
        assert staled == 2  # rockella-2411 and rockella-110

        # Check the stale flag
        row = get_listing_by_id(db_conn, "rockella-101")
        assert row["stale"] is False

        row = get_listing_by_id(db_conn, "rockella-2411")
        assert row["stale"] is True

    def test_mark_stale_respects_age_threshold(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)

        # Don't backdate — listings are fresh (just inserted)
        staled = mark_stale(db_conn, "rockella", {"rockella-101"})
        assert staled == 0  # Too recent to mark stale

    def test_mark_stale_ignores_other_sources(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)

        db_conn.execute("""
            UPDATE listings SET last_seen_at = datetime('now', '-8 days')
        """)
        db_conn.commit()

        # Mark stale for rockella only — gmdc and opendata should be untouched
        mark_stale(db_conn, "rockella", {"rockella-101"})

        row = get_listing_by_id(db_conn, "gmdc-greenpoint-1")
        assert row["stale"] is False  # Different source, unaffected


# ── Scrape run audit trail ────────────────────────────────────────────────────

class TestScrapeRuns:
    def test_start_and_finish_run(self, db_conn):
        run_id = start_scrape_run(db_conn, ["rockella", "nyc_opendata"])
        assert run_id is not None
        assert isinstance(run_id, int)

        finish_scrape_run(
            db_conn, run_id,
            listings_added=10,
            listings_updated=5,
            credits_used=4,
            errors=["minor error"],
            status="completed",
        )

        row = db_conn.execute("SELECT * FROM scrape_runs WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "completed"
        assert row["listings_added"] == 10
        assert row["listings_updated"] == 5
        assert row["credits_used"] == 4
        assert "minor error" in row["errors"]

    def test_failed_run(self, db_conn):
        run_id = start_scrape_run(db_conn, ["rockella"])
        finish_scrape_run(db_conn, run_id, errors=["fatal crash"], status="failed")

        row = db_conn.execute("SELECT * FROM scrape_runs WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "failed"


# ── Pagination tests ──────────────────────────────────────────────────────────

class TestPagination:
    def test_limit(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, limit=2)
        assert total == 5
        assert len(results) == 2

    def test_offset(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        page1, _ = query_listings(db_conn, limit=2, offset=0)
        page2, _ = query_listings(db_conn, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # No overlap
        page1_ids = {r["id"] for r in page1}
        page2_ids = {r["id"] for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_offset_beyond_results(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        results, total = query_listings(db_conn, limit=50, offset=100)
        assert total == 5
        assert len(results) == 0


# ── Stats tests ───────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_empty_db(self, db_conn):
        s = get_stats(db_conn)
        assert s["total_listings"] == 0
        assert s["active_listings"] == 0
        assert s["stale_listings"] == 0
        assert s["by_source"] == {}
        assert s["by_borough"] == {}

    def test_stats_with_data(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        s = get_stats(db_conn)
        assert s["total_listings"] == 5
        assert s["active_listings"] == 5
        assert s["stale_listings"] == 0
        assert s["by_source"]["rockella"] == 3
        assert s["by_source"]["nyc_opendata"] == 1
        assert s["by_source"]["gmdc"] == 1
        assert s["by_borough"]["brooklyn"] == 3

    def test_stats_with_stale(self, db_conn, sample_listings):
        _insert_samples(db_conn, sample_listings)
        db_conn.execute("UPDATE listings SET stale=1 WHERE id='rockella-101'")
        db_conn.commit()

        s = get_stats(db_conn)
        assert s["active_listings"] == 4
        assert s["stale_listings"] == 1


# ── Migration tests ───────────────────────────────────────────────────────────

class TestMigration:
    def test_import_from_json(self, db_conn):
        # Create a temporary JSON file
        data = {
            "generated_at": "2026-03-25T21:56:02Z",
            "total_listings": 2,
            "listings": [
                {
                    "id": "test-1",
                    "source": "test",
                    "source_url": "https://test.com/1",
                    "title": "Test Studio 1",
                    "address": "123 Test St, Brooklyn, NY",
                    "neighborhood": "Bushwick",
                    "borough": "brooklyn",
                    "price_monthly": 900.0,
                    "size_sqft": 200,
                    "photos": ["https://test.com/photo.jpg"],
                    "amenities": ["WiFi"],
                    "description": "A test studio",
                    "use_type": "studio",
                    "scraped_at": "2026-03-25T21:56:02Z",
                },
                {
                    "id": "test-2",
                    "source": "test",
                    "source_url": "https://test.com/2",
                    "title": "Test Studio 2",
                    "address": "456 Test Ave, Queens, NY",
                    "neighborhood": "Astoria",
                    "borough": "queens",
                    "price_monthly": 1100.0,
                    "size_sqft": 300,
                    "photos": [],
                    "amenities": [],
                    "description": "Another test studio",
                    "use_type": "studio",
                    "scraped_at": "2026-03-25T21:56:02Z",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            json_path = f.name

        try:
            counts = import_from_json(db_conn, json_path)
            assert counts["inserted"] == 2
            assert counts["skipped"] == 0

            # Verify data
            row = get_listing_by_id(db_conn, "test-1")
            assert row is not None
            assert row["title"] == "Test Studio 1"
            assert row["price_monthly"] == 900.0
            assert row["photos"] == ["https://test.com/photo.jpg"]

            # Re-import should update
            counts = import_from_json(db_conn, json_path)
            assert counts["updated"] == 2
            assert counts["inserted"] == 0
        finally:
            os.unlink(json_path)

    def test_import_skips_invalid(self, db_conn):
        data = {
            "listings": [
                {"id": "valid", "source": "test", "source_url": "https://test.com", "title": "Valid", "scraped_at": "2026-01-01T00:00:00Z"},
                {"bad_field": "no source or title"},  # Invalid
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            json_path = f.name

        try:
            counts = import_from_json(db_conn, json_path)
            assert counts["inserted"] == 1
            assert counts["skipped"] == 1
        finally:
            os.unlink(json_path)
