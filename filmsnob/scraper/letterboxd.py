"""Scrape Letterboxd user data (RSS, HTML, or CSV)."""

from __future__ import annotations

import csv
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from filmsnob.config import LETTERBOXD_BASE_URL, REQUEST_DELAY, REQUEST_TIMEOUT
from filmsnob.models import FilmEntry, UserProfile

logger = logging.getLogger(__name__)

RSS_NAMESPACES = {
    "letterboxd": "https://letterboxd.com",
    "tmdb": "https://themoviedb.org",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class LetterboxdScraper:
    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        })

    def scrape(self, username: str) -> UserProfile:
        logger.info("fetching rss for %s", username)
        url = f"{LETTERBOXD_BASE_URL}/{username}/rss/"
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("rss failed for %s: %s", username, exc)
            return UserProfile(username=username)

        root = ET.fromstring(resp.content)
        films: list[FilmEntry] = []
        seen_slugs: set[str] = set()

        for item in root.findall(".//item"):
            film = self._parse_rss_item(item)
            if film and film.letterboxd_slug not in seen_slugs:
                seen_slugs.add(film.letterboxd_slug or film.title)
                films.append(film)

        profile = UserProfile(username=username, films=films)
        logger.info("got %d films for %s", len(films), username)
        return profile

    def scrape_html(self, username: str) -> UserProfile:
        logger.info("html scraping %s", username)
        films = self._scrape_films(username)
        film_map = {f.letterboxd_slug: f for f in films}

        logger.info("found %d films, getting reviews", len(films))
        reviews = self._scrape_reviews(username)
        for slug, review_text in reviews.items():
            if slug in film_map:
                film_map[slug].review = review_text

        profile = UserProfile(username=username, films=list(film_map.values()))
        logger.info("html done: %d films for %s", len(films), username)
        return profile

    @staticmethod
    def from_csv_export(export_dir: str | Path, username: str = "csv_user") -> UserProfile:
        export_dir = Path(export_dir)
        film_map: dict[str, FilmEntry] = {}

        ratings_path = export_dir / "ratings.csv"
        if ratings_path.exists():
            for row in _read_csv(ratings_path):
                slug = _slug_from_uri(row.get("Letterboxd URI", ""))
                key = slug or f"{row['Name']}_{row.get('Year', '')}"
                film_map[key] = FilmEntry(
                    title=row["Name"],
                    year=_safe_int(row.get("Year")),
                    letterboxd_slug=slug,
                    rating=_safe_float(row.get("Rating")),
                )

        reviews_path = export_dir / "reviews.csv"
        if reviews_path.exists():
            for row in _read_csv(reviews_path):
                slug = _slug_from_uri(row.get("Letterboxd URI", ""))
                key = slug or f"{row['Name']}_{row.get('Year', '')}"
                if key in film_map:
                    film_map[key].review = row.get("Review", "")
                else:
                    film_map[key] = FilmEntry(
                        title=row["Name"],
                        year=_safe_int(row.get("Year")),
                        letterboxd_slug=slug,
                        rating=_safe_float(row.get("Rating")),
                        review=row.get("Review", ""),
                    )

        watched_path = export_dir / "watched.csv"
        if watched_path.exists():
            for row in _read_csv(watched_path):
                slug = _slug_from_uri(row.get("Letterboxd URI", ""))
                key = slug or f"{row['Name']}_{row.get('Year', '')}"
                if key not in film_map:
                    film_map[key] = FilmEntry(
                        title=row["Name"],
                        year=_safe_int(row.get("Year")),
                        letterboxd_slug=slug,
                        watched_date=row.get("Date", None),
                    )

        profile = UserProfile(username=username, films=list(film_map.values()))
        logger.info("csv import: %d films for %s", len(film_map), username)
        return profile

    @staticmethod
    def _parse_rss_item(item: ET.Element) -> Optional[FilmEntry]:
        ns = RSS_NAMESPACES
        film_title = item.findtext("letterboxd:filmTitle", "", ns)
        if not film_title:
            return None

        film_year = _safe_int(item.findtext("letterboxd:filmYear", "", ns))
        rating = _safe_float(item.findtext("letterboxd:memberRating", "", ns))
        liked = item.findtext("letterboxd:memberLike", "", ns) == "Yes"
        watched_date = item.findtext("letterboxd:watchedDate", "", ns) or None
        tmdb_id = _safe_int(item.findtext("tmdb:movieId", "", ns))

        link = item.findtext("link", "")
        slug_match = re.search(r"/film/([^/]+)/", link)
        slug = slug_match.group(1) if slug_match else None

        review = None
        desc = item.findtext("description", "")
        if desc:
            soup = BeautifulSoup(desc, "lxml")
            paragraphs = soup.find_all("p")
            review_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and not text.startswith("Watched on") and not p.find("img"):
                    review_parts.append(text)
            if review_parts:
                review = " ".join(review_parts)

        return FilmEntry(
            title=film_title,
            year=film_year,
            letterboxd_slug=slug,
            rating=rating,
            review=review,
            liked=liked,
            watched_date=watched_date,
            tmdb_id=tmdb_id,
        )

    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        time.sleep(self.delay)
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
            logger.warning("got %d from %s", resp.status_code, url)
        except requests.RequestException as exc:
            logger.error("request to %s failed: %s", url, exc)
        return None

    def _scrape_films(self, username: str) -> list[FilmEntry]:
        films: list[FilmEntry] = []
        page = 1
        while True:
            url = f"{LETTERBOXD_BASE_URL}/{username}/films/page/{page}/"
            soup = self._fetch(url)
            if soup is None:
                break

            posters = soup.select("li.poster-container")
            if not posters:
                break

            for container in posters:
                film = self._parse_poster(container)
                if film:
                    films.append(film)

            if not soup.select_one(".paginate-nextprev .next"):
                break
            page += 1

        return films

    def _scrape_reviews(self, username: str) -> dict[str, str]:
        reviews: dict[str, str] = {}
        page = 1
        while True:
            url = f"{LETTERBOXD_BASE_URL}/{username}/films/reviews/page/{page}/"
            soup = self._fetch(url)
            if soup is None:
                break

            entries = soup.select("li.film-detail")
            if not entries:
                break

            for entry in entries:
                slug, text = self._parse_review_entry(entry)
                if slug and text:
                    reviews[slug] = text

            if not soup.select_one(".paginate-nextprev .next"):
                break
            page += 1

        return reviews

    @staticmethod
    def _parse_poster(container) -> Optional[FilmEntry]:
        poster_div = container.select_one(".film-poster")
        if not poster_div:
            return None

        slug = poster_div.get("data-film-slug", "")
        img = poster_div.find("img")
        title = img.get("alt", "") if img else ""

        rating = None
        rating_el = container.select_one("[class*='rated-']")
        if rating_el:
            for cls in rating_el.get("class", []):
                m = re.match(r"rated-(\d+)", cls)
                if m:
                    rating = int(m.group(1)) / 2.0
                    break

        liked = bool(container.select_one(".like.has-liked"))

        return FilmEntry(
            title=title,
            letterboxd_slug=slug,
            rating=rating,
            liked=liked,
        )

    @staticmethod
    def _parse_review_entry(entry) -> tuple[Optional[str], Optional[str]]:
        link = entry.select_one("h2 a")
        if not link:
            return None, None

        href = link.get("href", "")
        slug_match = re.search(r"/film/([^/]+)/", href)
        slug = slug_match.group(1) if slug_match else None

        body = entry.select_one(".body-text")
        text = body.get_text(strip=True) if body else None

        return slug, text


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _slug_from_uri(uri: str) -> str:
    m = re.search(r"letterboxd\.com/film/([^/]+)", uri)
    return m.group(1) if m else ""


def _safe_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
