# FilmSnob

Content-based movie recommender that uses Letterboxd diary data and TMDB metadata to suggest films.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Add your TMDB API key to `.env`. You can get one at https://www.themoviedb.org/settings/api.

## Usage

Scrape all profiles and build the corpus:

```bash
python scripts/scrape_batch.py
python scripts/build_corpus.py
python scripts/build_embeddings.py
```

Get recommendations for a user:

```bash
python scripts/recommend.py --username <letterboxd_username>
```

Scrape a single user:

```bash
python scripts/scrape_user.py --username <letterboxd_username>
```

## Project structure

```
filmsnob/
  config.py          config from .env
  models.py          FilmEntry / UserProfile dataclasses
  pipeline.py        single-user scrape + enrich pipeline
  aggregate.py       merge profiles into one corpus
  scraper/
    letterboxd.py    RSS / HTML / CSV ingestion
    tmdb.py          TMDB API enrichment
  embedding/
    embed.py         SBERT + metadata + PCA embeddings
  recommend/
    recommender.py   cosine similarity recommendations
scripts/
  scrape_user.py     scrape one user
  scrape_batch.py    scrape all users in active_profiles.txt
  build_corpus.py    aggregate into film_corpus.json
  build_embeddings.py  build embeddings from corpus
  recommend.py       get recs for a user
```
