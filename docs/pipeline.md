# Pipeline

The pipeline is defined in `dvc.yaml` and orchestrated with [DVC](https://dvc.org/). Run it with:

```bash
dvc repro
```

DVC tracks dependencies between stages and only re-runs what has changed.

## Stages

```mermaid
graph LR
    A[init-db] --> C[extract-metadata]
    B[fetch-pages] --> C
    C --> D[fetch-details]
    D --> E[download-images]
    E --> F[compute-embeddings]
```

### 1. init-db

Creates the DuckDB schema with four tables: `metadata`, `images`, `image_tag`, and `embeddings`.

### 2. fetch-pages

Async crawl of the paginated listing pages from the Spotlight repository. Each page is saved as an HTML file under `data/html/`. The crawler auto-detects the total page count from the first page's pagination nav.

### 3. extract-metadata

Parses the saved HTML pages in parallel using `ProcessPoolExecutor` and BeautifulSoup. Extracts entry IDs from thumbnail links and inserts them into the `metadata` table.

### 4. fetch-details

For each entry in the `metadata` table, fetches the detail page asynchronously (concurrency: 20). Extracts:

- Title and date
- Image URLs with SHA-256 hashes
- Tags

Populates the `images` and `image_tag` tables.

### 5. download-images

Downloads the actual image files from the URLs in the `images` table. Records the local file path and pixel dimensions (width, height). Skips already-downloaded images.

### 6. compute-embeddings

Computes 512-dimensional [CLIP](https://openai.com/research/clip) embeddings (`openai/clip-vit-base-patch32`) for all downloaded images. Processes in batches of 32. Stores normalized vectors in the `embeddings` table.

## Database Schema

```sql
CREATE TABLE metadata (
    id VARCHAR PRIMARY KEY,
    date TIMESTAMP,
    title VARCHAR
);

CREATE TABLE images (
    id_meta VARCHAR REFERENCES metadata(id),
    url VARCHAR UNIQUE,
    sha256 VARCHAR,
    path VARCHAR,
    width INTEGER,
    height INTEGER,
    PRIMARY KEY (id_meta, url)
);

CREATE TABLE image_tag (
    id_meta VARCHAR REFERENCES metadata(id),
    tag VARCHAR,
    PRIMARY KEY (id_meta, tag)
);

CREATE TABLE embeddings (
    url VARCHAR PRIMARY KEY REFERENCES images(url),
    embedding FLOAT[512]
);
```

## Running Individual Stages

```bash
dvc repro <stage-name>
```

This runs the named stage and all upstream dependencies that need updating.
