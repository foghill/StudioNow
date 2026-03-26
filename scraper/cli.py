from __future__ import annotations

import json
import logging
import sys

import click

from .client import CreditExhaustedError, FirecrawlClient
from .config import Config
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


def _run_scrapers(
    source_names: list[str],
    config: Config,
    client: FirecrawlClient,
) -> list[ScraperResult]:
    """Run a list of scrapers and return their results."""
    results = []
    for name in source_names:
        try:
            cls = _import_scraper(name)
            scraper = cls(client=client, config=config)
            result = scraper.run()
            # Save raw data
            save_raw(
                name,
                [l.model_dump(mode="json") for l in result.listings],
                config,
            )
            results.append(result)
            click.echo(
                f"  {name}: {len(result.listings)} listings "
                f"({result.credits_used} credits, {len(result.errors)} errors)"
            )
        except CreditExhaustedError as e:
            click.echo(f"  {name}: STOPPED — {e}", err=True)
            break
        except Exception as e:
            click.echo(f"  {name}: FAILED — {e}", err=True)
            results.append(ScraperResult(source=name, errors=[str(e)]))
    return results


@click.group()
def cli():
    """Studio Now — NYC artist studio space scraper powered by Firecrawl."""
    pass


@cli.command()
@click.option("--source", "-s", help="Run a single source by name")
@click.option("--priority", "-p", type=click.Choice(["high", "medium", "low"]), help="Run all sources at a priority level")
@click.option("--all", "run_all", is_flag=True, help="Run all enabled sources")
@click.option("--include-restricted", is_flag=True, help="Include sources with ToS restrictions (Craigslist, StreetEasy)")
def run(source: str | None, priority: str | None, run_all: bool, include_restricted: bool):
    """Run scrapers to collect studio listings."""
    config = Config()
    try:
        config.validate()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    client = FirecrawlClient(config)

    if source:
        names = [source]
    elif priority:
        sources = config.get_sources(priority=priority, include_restricted=include_restricted)
        names = [s.name for s in sources]
    elif run_all:
        sources = config.get_sources(include_restricted=include_restricted)
        names = [s.name for s in sources]
    else:
        # Default: run high-priority sources
        sources = config.get_sources(priority="high")
        names = [s.name for s in sources]

    click.echo(f"Running scrapers: {', '.join(names)}")
    click.echo(f"Credit budget: {config.credit_limit}")
    click.echo()

    results = _run_scrapers(names, config, client)

    # Combine all listings and normalize
    all_listings = []
    total_errors = []
    total_credits = 0
    for r in results:
        all_listings.extend(r.listings)
        total_errors.extend(r.errors)
        total_credits += r.credits_used

    normalized, rejected = normalize_listings(all_listings)
    output_path = save_results(normalized, rejected, config)

    click.echo()
    click.echo("=== Summary ===")
    click.echo(f"Total listings collected: {len(all_listings)}")
    click.echo(f"After normalization:      {len(normalized)}")
    click.echo(f"Rejected:                 {len(rejected)}")
    click.echo(f"Credits used:             {total_credits}/{config.credit_limit}")
    click.echo(f"Errors:                   {len(total_errors)}")
    click.echo(f"Output: {output_path}")


@cli.command()
def credits():
    """Show current credit usage estimate."""
    config = Config()
    # Read raw data files to estimate credits used
    import os
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
    """Re-normalize existing raw data without re-scraping."""
    config = Config()
    import os
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
    output_path = save_results(normalized, rejected, config)
    click.echo(f"Normalized {len(normalized)} listings -> {output_path}")
    if rejected:
        click.echo(f"Rejected {len(rejected)} entries")


@cli.command()
def sources():
    """List available sources and their status."""
    config = Config()
    click.echo("Available sources:")
    click.echo()
    for s in config.get_sources(include_restricted=True):
        status = "RESTRICTED (use --include-restricted)" if s.restricted else "enabled"
        click.echo(f"  {s.name:<20} priority={s.priority:<8} {status}")


if __name__ == "__main__":
    cli()
