"""Scrape a user, enrich with TMDB, save to disk."""

from __future__ import annotations

import logging
from pathlib import Path

from filmsnob.config import DATA_DIR
from filmsnob.models import UserProfile
from filmsnob.scraper.letterboxd import LetterboxdScraper
from filmsnob.scraper.tmdb import TMDBEnricher

logger = logging.getLogger(__name__)


def run_pipeline(
    username: str | None = None,
    csv_export_dir: str | None = None,
    skip_enrich: bool = False,
    output_dir: str | Path | None = None,
) -> UserProfile:
    output_dir = Path(output_dir) if output_dir else DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if csv_export_dir:
        profile = LetterboxdScraper.from_csv_export(csv_export_dir, username=username or "csv_user")
    elif username:
        scraper = LetterboxdScraper()
        profile = scraper.scrape(username)
    else:
        raise ValueError("need username or csv_export_dir")

    name = profile.username

    raw_path = output_dir / f"{name}_raw.json"
    profile.save_json(raw_path)
    logger.info("saved raw profile to %s", raw_path)

    if not skip_enrich:
        enricher = TMDBEnricher()
        profile = enricher.enrich(profile)

    enriched_path = output_dir / f"{name}.json"
    csv_path = output_dir / f"{name}.csv"

    profile.save_json(enriched_path)
    profile.save_csv(csv_path)
    logger.info("saved enriched profile to %s, %s", enriched_path, csv_path)

    return profile
