"""FilmEntry and UserProfile dataclasses."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class FilmEntry:
    title: str
    year: Optional[int] = None
    letterboxd_slug: Optional[str] = None
    rating: Optional[float] = None
    review: Optional[str] = None
    liked: bool = False
    watched_date: Optional[str] = None
    tmdb_id: Optional[int] = None
    overview: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    director: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    original_language: Optional[str] = None
    tmdb_rating: Optional[float] = None
    vote_count: Optional[int] = None
    poster_path: Optional[str] = None

    @property
    def is_enriched(self) -> bool:
        return self.overview is not None

    @property
    def embedding_text(self) -> str:
        parts = []
        if self.overview:
            parts.append(self.overview)
        if self.genres:
            parts.append(f"Genres: {', '.join(self.genres)}")
        if self.director:
            parts.append(f"Directed by {self.director}")
        if self.keywords:
            parts.append(f"Keywords: {', '.join(self.keywords[:10])}")
        return " ".join(parts)


@dataclass
class UserProfile:
    username: str
    films: list[FilmEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "films": [asdict(f) for f in self.films],
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserProfile:
        films = [FilmEntry(**f) for f in data.get("films", [])]
        return cls(username=data["username"], films=films)

    def save_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path: str | Path) -> UserProfile:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_dataframe(self) -> pd.DataFrame:
        records = []
        for film in self.films:
            d = asdict(film)
            d["genres"] = "|".join(d["genres"])
            d["cast"] = "|".join(d["cast"])
            d["keywords"] = "|".join(d["keywords"])
            records.append(d)
        return pd.DataFrame(records)

    def save_csv(self, path: str | Path) -> None:
        self.to_dataframe().to_csv(path, index=False)

    @property
    def rated_films(self) -> list[FilmEntry]:
        return [f for f in self.films if f.rating is not None]

    @property
    def reviewed_films(self) -> list[FilmEntry]:
        return [f for f in self.films if f.review]

    def __len__(self) -> int:
        return len(self.films)

    def __repr__(self) -> str:
        return (
            f"UserProfile(username={self.username!r}, "
            f"films={len(self.films)}, "
            f"rated={len(self.rated_films)}, "
            f"reviewed={len(self.reviewed_films)})"
        )
