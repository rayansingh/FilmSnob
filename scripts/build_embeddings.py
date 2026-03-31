#!/usr/bin/env python3
"""Build film embeddings from the corpus."""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filmsnob.config import DATA_DIR
from filmsnob.embedding import FilmEmbedder


def main():
    parser = argparse.ArgumentParser(description="Build film embeddings with SBERT + PCA")
    parser.add_argument("--corpus", "-c", default=str(DATA_DIR / "film_corpus.json"))
    parser.add_argument("--output-dir", "-o", default=str(DATA_DIR / "embeddings"))
    parser.add_argument("--pca-dims", type=int, default=128)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with open(args.corpus) as f:
        corpus = json.load(f)

    print(f"Loaded {len(corpus)} films from {args.corpus}")

    embedder = FilmEmbedder(pca_dims=args.pca_dims)
    result = embedder.build_embeddings(corpus)
    embedder.save(result, args.output_dir)

    print(f"\nEmbedding complete:")
    print(f"  Films:             {len(result['tmdb_ids'])}")
    print(f"  Raw dimensions:    {result['raw_dim']}")
    print(f"  PCA dimensions:    {result['pca_dim']}")
    print(f"  Variance explained: {result['variance_explained']:.1%}")
    print(f"  Saved to:          {args.output_dir}/")


if __name__ == "__main__":
    main()
