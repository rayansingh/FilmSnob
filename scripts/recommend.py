#!/usr/bin/env python3
"""Recommend films for a Letterboxd user."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filmsnob.recommend import Recommender


def main():
    parser = argparse.ArgumentParser(description="FilmSnob: get recommendations for a Letterboxd user")
    parser.add_argument("--username", "-u", required=True, help="Letterboxd username")
    parser.add_argument("--top-n", "-n", type=int, default=20, help="Number of recommendations")
    parser.add_argument("--min-rating", type=float, default=0.0, help="Only use films rated >= this")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    rec = Recommender()
    results = rec.recommend(
        username=args.username,
        top_n=args.top_n,
        min_rating=args.min_rating,
    )

    if not results:
        print(f"No recommendations found for {args.username}")
        sys.exit(1)

    print(f"\nTop {len(results)} recommendations for @{args.username}:\n")
    for r in results:
        print(f"  {r['rank']:2d}. {r['title']}  (similarity: {r['similarity']:.3f})")


if __name__ == "__main__":
    main()
