"""Fetch plot, genres, cast, director, keywords from TMDB for each film."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from tqdm import tqdm

from filmsnob.config import TMDB_API_KEY, TMDB_BASE_URL, REQUEST_DELAY, REQUEST_TIMEOUT
from filmsnob.models import FilmEntry, UserProfile

logger = logging.getLogger(__name__)

MAX_CAST = 10
MAX_KEYWORDS = 15


class TMDBEnricher:
    def __init__(self, api_key: str = TMDB_API_KEY, delay: float = REQUEST_DELAY * 0.25):
        if not api_key:
            raise ValueError("missing TMDB_API_KEY in .env")
        self.api_key = api_key
        self.delay = delay
        self.session = requests.Session()
        if api_key.startswith("ey"):
            self.session.headers["Authorization"] = f"Bearer {api_key}"
            self._use_bearer = True
        else:
            self._use_bearer = False

    def enrich(self, profile: UserProfile) -> UserProfile:
        skipped = 0
        for film in tqdm(profile.films, desc="Enriching with TMDB"):
            if film.is_enriched:
                continue
            try:
                self._enrich_film(film)
            except Exception as exc:
                logger.warning("enrich failed for %s: %s", film.title, exc)
                skipped += 1
            time.sleep(self.delay)

        enriched = sum(1 for f in profile.films if f.is_enriched)
        logger.info("enriched %d/%d films (%d skipped)", enriched, len(profile.films), skipped)
        return profile

    def _get(self, endpoint: str, params: dict | None = None) -> Optional[dict]:
        params = params or {}
        if not self._use_bearer:
            params["api_key"] = self.api_key
        url = f"{TMDB_BASE_URL}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.debug("tmdb request failed: %s", exc)
            return None

    def _search_movie(self, title: str, year: Optional[int] = None) -> Optional[int]:
        params = {"query": title, "include_adult": "false"}
        if year:
            params["year"] = str(year)

        data = self._get("/search/movie", params)
        if not data or not data.get("results"):
            if year:
                return self._search_movie(title, year=None)
            return None

        return data["results"][0]["id"]

    def _enrich_film(self, film: FilmEntry) -> None:
        tmdb_id = film.tmdb_id or self._search_movie(film.title, film.year)
        if tmdb_id is None:
            logger.debug("no match for %s (%s)", film.title, film.year)
            return

        details = self._get(f"/movie/{tmdb_id}", {"append_to_response": "keywords,credits"})
        if details is None:
            return

        film.tmdb_id = tmdb_id
        film.overview = details.get("overview", "")
        film.genres = [g["name"] for g in details.get("genres", [])]
        film.original_language = details.get("original_language")
        film.tmdb_rating = details.get("vote_average")
        film.vote_count = details.get("vote_count")
        film.poster_path = details.get("poster_path")

        if not film.year:
            release = details.get("release_date", "")
            if release:
                film.year = int(release[:4])

        credits = details.get("credits", {})
        film.cast = [
            member["name"]
            for member in credits.get("cast", [])[:MAX_CAST]
        ]
        film.director = next(
            (
                member["name"]
                for member in credits.get("crew", [])
                if member.get("job") == "Director"
            ),
            None,
        )

        kw_data = details.get("keywords", {})
        film.keywords = [
            kw["name"]
            for kw in kw_data.get("keywords", [])[:MAX_KEYWORDS]
        ]
