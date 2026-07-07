# spotlight-ingest

Data ingestion pipeline that scrapes image metadata from a Spotlight repository, stores it in a DuckDB database, and downloads the images locally.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (recommended)

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

Or run each step individually:

| Command          | Description                                      |
|------------------|--------------------------------------------------|
| `make repo`      | Fetch HTML listing pages from the repository     |
| `make list-html` | Parse HTML pages and extract metadata into DuckDB|
| `make img`       | Download images and record dimensions            |
| `make clean`     | Remove downloaded HTML and the metadata database |

## Pipeline

1. **Fetch pages** (`scripts/repo_access.py`) -- Async crawl of paginated listing pages, saved as HTML files.
2. **Extract metadata** (`scripts/process_pages.py`) -- Parse the HTML to extract entry IDs into a DuckDB `metadata` table.
3. **Fetch details** (`scripts/download_image.py`) -- For each entry, fetch the detail page, extract title, date, tags, and image URLs with SHA-256 hashes.
4. **Download images** (`scripts/store_image.py`) -- Download images, record file path and dimensions in the `images` table.

## Testing

```bash
make test
```

## Project Structure

```
config.py          # Paths and environment variables
scripts/
  repo_access.py   # Async page crawler
  process_pages.py # HTML parser -> DuckDB metadata
  download_image.py# Detail page scraper
  store_image.py   # Image downloader
data/
  html/            # Cached HTML pages
  images/          # Downloaded images
  metadata.db      # DuckDB database
```
