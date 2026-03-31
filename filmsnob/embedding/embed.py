"""SBERT + metadata embeddings with PCA reduction."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

ALL_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
    "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery",
    "Romance", "Science Fiction", "TV Movie", "Thriller", "War", "Western",
]
GENRE_INDEX = {g: i for i, g in enumerate(ALL_GENRES)}

SBERT_MODEL = "all-MiniLM-L6-v2"
SBERT_DIM = 384


class FilmEmbedder:
    def __init__(
        self,
        model_name: str = SBERT_MODEL,
        pca_dims: int = 128,
        batch_size: int = 64,
    ):
        self.model = SentenceTransformer(model_name)
        self.pca_dims = pca_dims
        self.batch_size = batch_size
        self.pca: Optional[PCA] = None
        self.scaler: Optional[StandardScaler] = None

    def build_embeddings(self, corpus: list[dict]) -> dict:
        logger.info("encoding %d films", len(corpus))

        content_vecs = self._encode_content(corpus)
        review_vecs = self._encode_reviews(corpus)
        meta_matrix = self._build_metadata(corpus)

        raw = np.hstack([content_vecs, review_vecs, meta_matrix])
        logger.info("raw shape: %s", raw.shape)

        self.scaler = StandardScaler()
        scaled = self.scaler.fit_transform(raw)

        self.pca = PCA(n_components=min(self.pca_dims, scaled.shape[0], scaled.shape[1]))
        reduced = self.pca.fit_transform(scaled)

        explained = self.pca.explained_variance_ratio_.sum()
        logger.info("pca %d -> %d dims (%.1f%% var)", raw.shape[1], reduced.shape[1], explained * 100)

        tmdb_ids = [film["tmdb_id"] for film in corpus]
        titles = [f"{film['title']} ({film.get('year', '?')})" for film in corpus]

        return {
            "embeddings": reduced,
            "tmdb_ids": tmdb_ids,
            "titles": titles,
            "raw_dim": raw.shape[1],
            "pca_dim": reduced.shape[1],
            "variance_explained": float(explained),
            "pca": self.pca,
            "scaler": self.scaler,
        }

    def _encode_content(self, corpus: list[dict]) -> np.ndarray:
        texts = []
        for film in corpus:
            t = film.get("embedding_text", "")
            texts.append(t if t else "unknown film")

        logger.info("encoding %d content texts", len(texts))
        return self.model.encode(texts, batch_size=self.batch_size, show_progress_bar=True)

    def _encode_reviews(self, corpus: list[dict]) -> np.ndarray:
        result = np.zeros((len(corpus), SBERT_DIM), dtype=np.float32)
        to_encode = []
        indices = []

        for i, film in enumerate(corpus):
            reviews = film.get("review_texts", [])
            if reviews:
                for r in reviews:
                    to_encode.append(r)
                    indices.append(i)

        if to_encode:
            logger.info("encoding %d reviews", len(to_encode))
            review_vecs = self.model.encode(
                to_encode, batch_size=self.batch_size, show_progress_bar=True,
            )

            counts = np.zeros(len(corpus), dtype=np.float32)
            for vec, idx in zip(review_vecs, indices):
                result[idx] += vec
                counts[idx] += 1

            mask = counts > 0
            result[mask] /= counts[mask, np.newaxis]

        films_with = np.count_nonzero(result.any(axis=1))
        logger.info("%d/%d films have reviews", films_with, len(corpus))

        return result

    def _build_metadata(self, corpus: list[dict]) -> np.ndarray:
        n = len(corpus)
        n_scalar = 4
        n_genre = len(ALL_GENRES)
        meta = np.zeros((n, n_scalar + n_genre), dtype=np.float32)

        for i, film in enumerate(corpus):
            year = film.get("year")
            meta[i, 0] = year if year else 0

            avg_rating = film.get("avg_user_rating")
            meta[i, 1] = avg_rating if avg_rating else 0

            tmdb_rating = film.get("tmdb_rating")
            meta[i, 2] = tmdb_rating if tmdb_rating else 0

            vote_count = film.get("vote_count")
            meta[i, 3] = np.log1p(vote_count) if vote_count else 0

            for g in film.get("genres", []):
                if g in GENRE_INDEX:
                    meta[i, n_scalar + GENRE_INDEX[g]] = 1.0

        return meta

    def save(self, result: dict, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        np.save(output_dir / "embeddings.npy", result["embeddings"])
        np.save(output_dir / "tmdb_ids.npy", np.array(result["tmdb_ids"]))

        index = {
            tid: {"index": i, "title": title}
            for i, (tid, title) in enumerate(zip(result["tmdb_ids"], result["titles"]))
        }
        with open(output_dir / "index.json", "w") as f:
            json.dump(index, f, indent=2)

        meta = {
            "raw_dim": result["raw_dim"],
            "pca_dim": result["pca_dim"],
            "variance_explained": result["variance_explained"],
            "num_films": len(result["tmdb_ids"]),
            "sbert_model": SBERT_MODEL,
            "components": {
                "content_sbert": SBERT_DIM,
                "review_sbert": SBERT_DIM,
                "year": 1,
                "avg_user_rating": 1,
                "tmdb_rating": 1,
                "log_vote_count": 1,
                "genre_multihot": len(ALL_GENRES),
            },
        }
        with open(output_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        logger.info("wrote embeddings to %s", output_dir)
