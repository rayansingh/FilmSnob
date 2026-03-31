"""Recommend films by cosine similarity to a user's profile vector."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from filmsnob.config import DATA_DIR
from filmsnob.scraper.letterboxd import LetterboxdScraper

logger = logging.getLogger(__name__)


class Recommender:
    def __init__(self, embeddings_dir: str | Path | None = None):
        embeddings_dir = Path(embeddings_dir) if embeddings_dir else DATA_DIR / "embeddings"
        self.embeddings = np.load(embeddings_dir / "embeddings.npy")
        self.tmdb_ids = np.load(embeddings_dir / "tmdb_ids.npy")

        with open(embeddings_dir / "index.json") as f:
            self.index = json.load(f)

        self.id_to_row = {int(tid): i for i, tid in enumerate(self.tmdb_ids)}

    def recommend(
        self,
        username: str,
        top_n: int = 20,
        min_rating: float = 0.0,
    ) -> list[dict]:
        scraper = LetterboxdScraper()
        profile = scraper.scrape(username)

        if not profile.films:
            logger.warning("no films for %s", username)
            return []

        user_vec, watched_ids = self._build_user_vector(profile, min_rating)
        if user_vec is None:
            logger.warning("no rated films in corpus for %s", username)
            return []

        sims = cosine_similarity(user_vec.reshape(1, -1), self.embeddings)[0]

        candidate_indices = [
            i for i in range(len(self.tmdb_ids))
            if int(self.tmdb_ids[i]) not in watched_ids
        ]

        ranked = sorted(candidate_indices, key=lambda i: sims[i], reverse=True)

        results = []
        for i in ranked[:top_n]:
            tid = str(int(self.tmdb_ids[i]))
            entry = self.index.get(tid, {})
            results.append({
                "rank": len(results) + 1,
                "tmdb_id": int(tid),
                "title": entry.get("title", "Unknown"),
                "similarity": float(sims[i]),
            })

        return results

    def recommend_from_ratings(
        self,
        ratings: dict[int, float],
        top_n: int = 20,
    ) -> list[dict]:
        user_vec = self._vector_from_ratings(ratings)
        if user_vec is None:
            return []

        sims = cosine_similarity(user_vec.reshape(1, -1), self.embeddings)[0]
        watched_ids = set(ratings.keys())

        candidate_indices = [
            i for i in range(len(self.tmdb_ids))
            if int(self.tmdb_ids[i]) not in watched_ids
        ]

        ranked = sorted(candidate_indices, key=lambda i: sims[i], reverse=True)

        results = []
        for i in ranked[:top_n]:
            tid = str(int(self.tmdb_ids[i]))
            entry = self.index.get(tid, {})
            results.append({
                "rank": len(results) + 1,
                "tmdb_id": int(tid),
                "title": entry.get("title", "Unknown"),
                "similarity": float(sims[i]),
            })

        return results

    def _build_user_vector(self, profile, min_rating: float) -> tuple[Optional[np.ndarray], set[int]]:
        watched_ids = set()
        weights = []
        vectors = []

        for film in profile.films:
            if film.tmdb_id:
                watched_ids.add(film.tmdb_id)

            if film.tmdb_id and film.rating and film.rating >= min_rating:
                row = self.id_to_row.get(film.tmdb_id)
                if row is not None:
                    vectors.append(self.embeddings[row])
                    weights.append(film.rating)

        if not vectors:
            return None, watched_ids

        weights = np.array(weights, dtype=np.float32)
        vectors = np.array(vectors, dtype=np.float32)
        user_vec = np.average(vectors, axis=0, weights=weights)

        return user_vec, watched_ids

    def _vector_from_ratings(self, ratings: dict[int, float]) -> Optional[np.ndarray]:
        weights = []
        vectors = []

        for tmdb_id, rating in ratings.items():
            row = self.id_to_row.get(tmdb_id)
            if row is not None:
                vectors.append(self.embeddings[row])
                weights.append(rating)

        if not vectors:
            return None

        weights = np.array(weights, dtype=np.float32)
        vectors = np.array(vectors, dtype=np.float32)
        return np.average(vectors, axis=0, weights=weights)
