from __future__ import annotations

import json
import logging
import os
import sys

import click

from .client import CreditExhaustedError, FirecrawlClient
from .config import Config
from .db import (
    finish_scrape_run,
    get_connection,
    get_stats,
    import_from_json,
    init_db,
    mark_stale,
    start_scrape_run,
    upsert_listings,
)
from .models import ScraperResult
from .normalize import normalize_listings, save_raw, save_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Scraper class registry — lazy imports to avoid loading all scrapers at startup
SCRAPER_CLASSES = {
    "rockella": "scraper.sources.rockella:RockellaScraper",
    "chashama": "scraper.sources.chashama:ChashamaScraper",
    "spacefinder": "scraper.sources.spacefinder:SpacefinderScraper",
    "loopnet": "scraper.sources.loopnet:LoopnetScraper",
    "nyfa": "scraper.sources.nyfa:NyfaScraper",
    "listings_project": "scraper.sources.listings_project:ListingsProjectScraper",
    "craigslist": "scraper.sources.craigslist:CraigslistScraper",
    "streeteasy": "scraper.sources.streeteasy:StreeteasyScraper",
    "nyc_opendata": "scraper.sources.nyc_opendata:NycOpendataScraper",
    "coworker": "scraper.sources.coworker:CoworkerScraper",
    "ny_studio_factory": "scraper.sources.ny_studio_factory:NyStudioFactoryScraper",
    "navy_yard": "scraper.sources.navy_yard:NavyYardScraper",
    "gmdc": "scraper.sources.gmdc:GmdcScraper",
    "mana_contemporary": "scraper.sources.mana_contemporary:ManaContemporaryScraper",
    "pioneer_works": "scraper.sources.pioneer_works:PioneerWorksScraper",
    "industry_city": "scraper.sources.industry_city:IndustryCityScraper",
}


def _import_scraper(name: str):
    """Dynamically import a scraper class."""
    path = SCRAPER_CLASSES.get(name)
    if not path:
        raise ValueError(f"Unknown source: {name}")
    module_path, class_name = path.rsplit(":", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@click.group()
def cli():
    """Studio Now — NYC artist studio space scraper powered by Firecrawl."""
    pass


@cli.command()
@click.option("--source", "-s", help="Run a single source by name")
@click.option("--priority", "-p", type=click.Choice(["high", "medium", "low"]), help="Run all sources at a priority level")
@click.option("--all", "run_all", is_flag=True, help="Run all enabled sources")
@click.option("--include-restricted", is_flag=True, help="Include sources with ToS restrictions")
def run(source: str | None, priority: str | None, run_all: bool, include_restricted: bool):
    """Run scrapers and write results to SQLite database."""
    config = Config()
    try:
        config.validate()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    client = FirecrawlClient(config)
    conn = get_connection(config=config)
    init_db(conn)

    if source:
        names = [source]
    elif priority:
        names = [s.name for s in config.get_sources(priority=priority, include_restricted=include_restricted)]
    elif run_all:
        names = [s.name for s in config.get_sources(include_restricted=include_restricted)]
    else:
        names = [s.name for s in config.get_sources(priority="high")]

    click.echo(f"Running scrapers: {', '.join(names)}")
    click.echo(f"Credit budget: {config.credit_limit}")
    click.echo()

    run_id = start_scrape_run(conn, names)
    total_inserted = 0
    total_updated = 0
    total_staled = 0
    total_credits = 0
    total_errors: list[str] = []

    for name in names:
        try:
            cls = _import_scraper(name)
            scraper = cls(client=client, config=config)
            result = scraper.run()

            # Save raw data
            save_raw(name, [l.model_dump(mode="json") for l in result.listings], config)

            # Normalize
            normalized, rejected = normalize_listings(result.listings)

            # Also save JSON for backwards compat
            save_results(normalized, rejected, config)

            # Upsert into SQLite
            counts = upsert_listings(conn, normalized)
            total_inserted += counts["inserted"]
            total_updated += counts["updated"]

            # Mark stale
            seen_ids = {l.id for l in normalized if l.id}
            staled = mark_stale(conn, name, seen_ids)
            total_staled += staled

            total_credits += result.credits_used
            total_errors.extend(result.errors)

            click.echo(
                f"  {name}: {len(normalized)} listings "
                f"({counts['inserted']} new, {counts['updated']} updated, "
                f"{result.credits_used} credits, {len(result.errors)} errors)"
            )
        except CreditExhaustedError as e:
            click.echo(f"  {name}: STOPPED — {e}", err=True)
            total_errors.append(str(e))
            break
        except Exception as e:
            click.echo(f"  {name}: FAILED — {e}", err=True)
            total_errors.append(f"{name}: {e}")

    finish_scrape_run(
        conn, run_id,
        listings_added=total_inserted,
        listings_updated=total_updated,
        listings_staled=total_staled,
        credits_used=total_credits,
        errors=total_errors,
        status="completed",
    )

    stats = get_stats(conn)
    conn.close()

    click.echo()
    click.echo("=== Summary ===")
    click.echo(f"New listings:        {total_inserted}")
    click.echo(f"Updated listings:    {total_updated}")
    click.echo(f"Staled listings:     {total_staled}")
    click.echo(f"Credits used:        {total_credits}/{config.credit_limit}")
    click.echo(f"Errors:              {len(total_errors)}")
    click.echo(f"DB total (active):   {stats['active_listings']}")
    click.echo(f"DB total (all):      {stats['total_listings']}")


@cli.command()
def credits():
    """Show current credit usage estimate."""
    config = Config()
    raw_dir = os.path.join(config.data_dir, "raw")
    if not os.path.exists(raw_dir):
        click.echo("No scraping runs found yet.")
        return
    files = sorted(os.listdir(raw_dir))
    click.echo(f"Raw data files: {len(files)}")
    for f in files:
        path = os.path.join(raw_dir, f)
        size = os.path.getsize(path)
        click.echo(f"  {f} ({size:,} bytes)")


@cli.command("normalize")
def normalize_cmd():
    """Re-normalize existing raw data and write to SQLite."""
    config = Config()
    raw_dir = os.path.join(config.data_dir, "raw")
    if not os.path.exists(raw_dir):
        click.echo("No raw data found. Run scrapers first.", err=True)
        sys.exit(1)

    from .models import StudioListing
    all_listings = []
    for filename in sorted(os.listdir(raw_dir)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(raw_dir, filename)
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                try:
                    all_listings.append(StudioListing(**item))
                except Exception:
                    pass

    if not all_listings:
        click.echo("No valid listings found in raw data.", err=True)
        sys.exit(1)

    normalized, rejected = normalize_listings(all_listings)

    # Write to JSON (backwards compat)
    output_path = save_results(normalized, rejected, config)

    # Write to SQLite
    conn = get_connection(config=config)
    init_db(conn)
    counts = upsert_listings(conn, normalized)
    stats = get_stats(conn)
    conn.close()

    click.echo(f"Normalized {len(normalized)} listings")
    click.echo(f"  SQLite: {counts['inserted']} new, {counts['updated']} updated")
    click.echo(f"  JSON:   {output_path}")
    click.echo(f"  DB total: {stats['active_listings']} active")
    if rejected:
        click.echo(f"  Rejected: {len(rejected)} entries")


@cli.command()
def sources():
    """List available sources and their status."""
    config = Config()
    click.echo("Available sources:")
    click.echo()
    for s in config.get_sources(include_restricted=True):
        status = "RESTRICTED (use --include-restricted)" if s.restricted else "enabled"
        click.echo(f"  {s.name:<20} priority={s.priority:<8} {status}")


@cli.command()
def stats():
    """Show database statistics."""
    config = Config()
    conn = get_connection(config=config)
    init_db(conn)
    s = get_stats(conn)
    conn.close()

    click.echo(f"Active listings: {s['active_listings']}")
    click.echo(f"Stale listings:  {s['stale_listings']}")
    click.echo(f"Total listings:  {s['total_listings']}")
    click.echo(f"With coords:     {s['with_coordinates']}")
    click.echo(f"Last scrape:     {s['last_scrape'] or 'never'}")
    click.echo()
    if s["by_source"]:
        click.echo("By source:")
        for src, cnt in sorted(s["by_source"].items(), key=lambda x: -x[1]):
            click.echo(f"  {src:<20} {cnt}")
    click.echo()
    if s["by_borough"]:
        click.echo("By borough:")
        for boro, cnt in sorted(s["by_borough"].items(), key=lambda x: -x[1]):
            click.echo(f"  {boro:<20} {cnt}")


@cli.command()
@click.argument("json_path", required=False)
def migrate(json_path: str | None):
    """Import existing listings.json into SQLite database."""
    config = Config()

    if not json_path:
        json_path = os.path.join(config.data_dir, "normalized", "listings.json")

    if not os.path.exists(json_path):
        click.echo(f"File not found: {json_path}", err=True)
        sys.exit(1)

    conn = get_connection(config=config)
    init_db(conn)
    counts = import_from_json(conn, json_path)
    s = get_stats(conn)
    conn.close()

    click.echo(f"Migration complete:")
    click.echo(f"  Inserted: {counts['inserted']}")
    click.echo(f"  Updated:  {counts['updated']}")
    click.echo(f"  Skipped:  {counts['skipped']}")
    click.echo(f"  DB total: {s['active_listings']} active listings")


if __name__ == "__main__":
    cli()
