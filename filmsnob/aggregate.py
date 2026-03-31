"""Merge per-user profiles into one film corpus, pooling reviews."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from filmsnob.models import UserProfile

logger = logging.getLogger(__name__)


def aggregate_profiles(profiles_dir: str | Path, output_path: str | Path) -> list[dict]:
    profiles_dir = Path(profiles_dir)
    output_path = Path(output_path)

    jsons = sorted(
        p for p in profiles_dir.glob("*.json")
        if not p.name.endswith("_raw.json")
    )
    logger.info("loading %d profiles", len(jsons))

    film_map: dict[int, dict] = {}
    film_reviews: dict[int, list[dict]] = defaultdict(list)

    for jp in jsons:
        profile = UserProfile.load_json(jp)
        for film in profile.films:
            if not film.tmdb_id:
                continue

            tid = film.tmdb_id

            if tid not in film_map:
                film_map[tid] = {
                    "tmdb_id": tid,
                    "title": film.title,
                    "year": film.year,
                    "overview": film.overview,
                    "genres": film.genres,
                    "director": film.director,
                    "cast": film.cast,
                    "keywords": film.keywords,
                    "original_language": film.original_language,
                    "tmdb_rating": film.tmdb_rating,
                    "vote_count": film.vote_count,
                    "embedding_text": film.embedding_text,
                }

            if film.review:
                film_reviews[tid].append({
                    "username": profile.username,
                    "rating": film.rating,
                    "review": film.review,
                })
            elif film.rating is not None:
                film_reviews[tid].append({
                    "username": profile.username,
                    "rating": film.rating,
                    "review": None,
                })

    corpus = []
    for tid, meta in film_map.items():
        entries = film_reviews.get(tid, [])
        ratings = [e["rating"] for e in entries if e["rating"] is not None]
        reviews = [e["review"] for e in entries if e["review"]]

        meta["user_entries"] = entries
        meta["review_texts"] = reviews
        meta["avg_user_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        meta["num_ratings"] = len(ratings)
        meta["num_reviews"] = len(reviews)
        corpus.append(meta)

    corpus.sort(key=lambda x: x["num_ratings"], reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)

    total_reviews = sum(c["num_reviews"] for c in corpus)
    multi = sum(1 for c in corpus if c["num_reviews"] > 1)
    logger.info("%d films, %d reviews, %d multi-review", len(corpus), total_reviews, multi)

    return corpus
