# Config

Project-wide configuration loaded from `config.py`. Environment variables are read from a `.env` file via `python-dotenv`.

## Environment Variables

| Variable | Source | Description |
|---|---|---|
| `SPOTLIGHT_REPO` | `.env` | Hostname of the Spotlight repository (e.g. `windows10spotlight.com`) |

## Paths

All paths are relative to the project root.

| Variable | Value | Description |
|---|---|---|
| `ROOT` | `.` | Project root directory |
| `DATA` | `data/` | Parent directory for all data artifacts |
| `LOGS` | `logs/` | Directory for log files |
| `metadata` | `data/metadata.db` | DuckDB database file |
| `IMG` | `data/images/` | Downloaded images directory |

## HTTP Headers

The `HEADERS` dict is shared across all scripts that make HTTP requests. It sets a browser-like `User-Agent` to avoid 403 responses from the Spotlight server.

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
}
```

## Setup

Create a `.env` file at the project root:

```
SPOTLIGHT_REPO=windows10spotlight.com
```

The file is loaded at import time with `override=True`, so environment variables set in `.env` take precedence over system-level ones.

::: config
