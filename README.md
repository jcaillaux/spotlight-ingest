# spotlight-ingest

[![Tests](https://github.com/jcaillaux/spotlight-ingest/actions/workflows/tests.yml/badge.svg)](https://github.com/jcaillaux/spotlight-ingest/actions/workflows/tests.yml)
[![Docs](https://github.com/jcaillaux/spotlight-ingest/actions/workflows/docs.yml/badge.svg)](https://jcaillaux.github.io/spotlight-ingest/)

Data ingestion pipeline that scrapes image metadata from a Spotlight repository, stores it in a DuckDB database, downloads the images locally, and computes CLIP embeddings.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

Create a `.env` file with:

```
SPOTLIGHT_REPO=<hostname of the spotlight repository>
```

## Usage

Run the full pipeline:

```bash
make all
```

This calls `dvc repro` under the hood, which only re-runs stages whose dependencies have changed.

To reset all downloaded data and the database:

```bash
make clean
```

Run tests:

```bash
make test
```

Run tests with coverage:

```bash
uv run python -m pytest --cov=scripts --cov=config --cov-report=term-missing tests
```

## Pipeline

The pipeline is defined in `dvc.yaml` and has six stages:

| Stage | Script | Description |
|---|---|---|
| `init-db` | `scripts/init_db.py` | Create the DuckDB schema (metadata, images, image_tag, embeddings) |
| `fetch-pages` | `scripts/repo_access.py` | Async crawl of paginated listing pages, saved as HTML files |
| `extract-metadata` | `scripts/process_pages.py` | Parse HTML pages in parallel to extract entry IDs into DuckDB |
| `fetch-details` | `scripts/fetch_details.py` | Fetch detail pages, extract title, date, tags, and image URLs |
| `download-images` | `scripts/store_image.py` | Download images and record file path and dimensions |
| `compute-embeddings` | `scripts/compute_embeddings.py` | Compute CLIP embeddings (openai/clip-vit-base-patch32) |

Run a single stage and its dependencies:

```bash
dvc repro <stage-name>
```

## Project Structure

```
config.py            # Paths, env variables, shared HTTP headers
dvc.yaml             # DVC pipeline definition
Makefile             # Convenience targets (all, clean, test)
scripts/
  init_db.py         # Database schema creation
  repo_access.py     # Async page crawler
  process_pages.py   # Parallel HTML parser -> DuckDB metadata
  fetch_details.py   # Detail page scraper
  store_image.py     # Image downloader
  compute_embeddings.py  # CLIP embedding computation
tests/
  test_config.py     # Config validation
  test_unit.py       # Unit tests (pure functions)
  test_integration.py# Integration tests (DB, file I/O, model)
data/
  html/              # Cached HTML pages
  images/            # Downloaded images
  metadata.db        # DuckDB database
```
