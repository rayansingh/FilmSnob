#!/usr/bin/env python3
"""Scrape one Letterboxd user, optionally enrich with TMDB."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filmsnob.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="FilmSnob: Letterboxd → enriched film data")
    parser.add_argument("--username", "-u", help="Letterboxd username to scrape")
    parser.add_argument("--csv-export", "-c", help="Path to unzipped Letterboxd data export")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip TMDB enrichment")
    parser.add_argument("--output-dir", "-o", default=None, help="Output directory (default: data/)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.username and not args.csv_export:
        parser.error("Provide --username (web scrape) or --csv-export (CSV import)")

    profile = run_pipeline(
        username=args.username,
        csv_export_dir=args.csv_export,
        skip_enrich=args.skip_enrich,
        output_dir=args.output_dir,
    )

    print(f"\nDone! {profile}")
    print(f"  Rated:    {len(profile.rated_films)}")
    print(f"  Reviewed: {len(profile.reviewed_films)}")
    enriched = sum(1 for f in profile.films if f.is_enriched)
    print(f"  Enriched: {enriched}/{len(profile.films)}")


if __name__ == "__main__":
    main()
