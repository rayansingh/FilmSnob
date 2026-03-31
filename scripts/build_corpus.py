#!/usr/bin/env python3
"""Merge scraped profiles into one film corpus."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filmsnob.config import DATA_DIR
from filmsnob.aggregate import aggregate_profiles


def main():
    parser = argparse.ArgumentParser(description="Aggregate user profiles into film corpus")
    parser.add_argument("--profiles-dir", "-p", default=str(DATA_DIR / "profiles"))
    parser.add_argument("--output", "-o", default=str(DATA_DIR / "film_corpus.json"))
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    corpus = aggregate_profiles(args.profiles_dir, args.output)

    print(f"\nCorpus built: {len(corpus)} unique films")
    print(f"  Total reviews:     {sum(c['num_reviews'] for c in corpus)}")
    print(f"  Multi-review films: {sum(1 for c in corpus if c['num_reviews'] > 1)}")
    print(f"  With embedding_text: {sum(1 for c in corpus if c.get('embedding_text'))}")
    print(f"\nSaved to {args.output}")

    print("\nTop 10 most-reviewed films:")
    for c in corpus[:10]:
        print(f"  {c['title']} ({c['year']}) - {c['num_reviews']} reviews, avg {c['avg_user_rating']}*")


if __name__ == "__main__":
    main()
