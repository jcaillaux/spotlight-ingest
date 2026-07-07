# spotlight-ingest

Data ingestion pipeline that scrapes image metadata from a Spotlight repository, stores it in a DuckDB database, downloads the images locally, and computes CLIP embeddings.

## Quick Start

```bash
uv sync
```

Create a `.env` file:

```
SPOTLIGHT_REPO=<hostname of the spotlight repository>
```

Run the full pipeline:

```bash
make all
```

## Features

- **Async I/O** with `aiohttp` for fast page crawling and image downloads
- **Parallel processing** with `ProcessPoolExecutor` for HTML parsing
- **DuckDB** for lightweight, embedded metadata storage
- **CLIP embeddings** for image similarity search
- **DVC pipeline** for reproducible, dependency-aware execution
- **Comprehensive tests** following TAP and Tiger Style testing philosophies
