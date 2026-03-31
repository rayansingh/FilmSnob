#!/usr/bin/env python3
"""Batch-scrape all profiles in data/active_profiles.txt and enrich with TMDB."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filmsnob.config import DATA_DIR
from filmsnob.models import UserProfile
from filmsnob.scraper.letterboxd import LetterboxdScraper
from filmsnob.scraper.tmdb import TMDBEnricher

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Batch scrape Letterboxd profiles")
    parser.add_argument(
        "--profiles", "-p",
        default=str(DATA_DIR / "active_profiles.txt"),
        help="Path to text file with one username per line",
    )
    parser.add_argument("--skip-enrich", action="store_true", help="Skip TMDB enrichment")
    parser.add_argument("--resume", action="store_true", help="Skip users whose JSON already exists")
    parser.add_argument("--output-dir", "-o", default=str(DATA_DIR / "profiles"))
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    profiles_path = Path(args.profiles)
    if not profiles_path.exists():
        print(f"file not found: {profiles_path}")
        sys.exit(1)

    usernames = [
        line.strip()
        for line in profiles_path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    print(f"Loaded {len(usernames)} usernames from {profiles_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scraper = LetterboxdScraper()
    enricher = None if args.skip_enrich else TMDBEnricher()

    succeeded, failed, skipped = 0, 0, 0

    for i, username in enumerate(usernames, 1):
        json_path = output_dir / f"{username}.json"

        if args.resume and json_path.exists():
            skipped += 1
            continue

        print(f"\n[{i}/{len(usernames)}] Scraping {username}...")
        try:
            profile = scraper.scrape(username)

            if not profile.films:
                logger.warning("no films for %s, skipping", username)
                failed += 1
                continue

            profile.save_json(output_dir / f"{username}_raw.json")

            if enricher:
                enricher.enrich(profile)

            profile.save_json(json_path)
            profile.save_csv(output_dir / f"{username}.csv")

            succeeded += 1
            print(
                f"  -> {len(profile.films)} films, "
                f"{len(profile.rated_films)} rated, "
                f"{len(profile.reviewed_films)} reviewed"
            )

        except KeyboardInterrupt:
            print("\ninterrupted, rerun with --resume to continue")
            break
        except Exception as exc:
            logger.error("failed on %s: %s", username, exc)
            failed += 1

    print(f"\nDone! Succeeded: {succeeded}, Failed: {failed}, Skipped: {skipped}")
    print(f"Data saved in {output_dir}/")


if __name__ == "__main__":
    main()
