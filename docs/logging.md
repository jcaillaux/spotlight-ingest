# Logging

The project uses [Loguru](https://github.com/Delgan/loguru) for structured, human-readable logging across all pipeline stages.

## Why Loguru

Loguru replaces Python's standard `logging` module with a simpler API:

- **Zero configuration** — no handlers, formatters, or boilerplate to set up
- **Colored output** — log levels are color-coded in the terminal
- **Log levels as methods** — `logger.info()`, `logger.warning()`, `logger.success()`
- **File rotation** — built-in rotation by size with `logger.add(path, rotation="5 MB")`
- **f-string friendly** — lazy formatting with `logger.info(f"Found {count} items")`

## Log Levels Used

| Level | Purpose | Example |
|---|---|---|
| `logger.info()` | Progress updates, stage start | `Found 42 HTML files to process` |
| `logger.success()` | Stage completion, timing | `Done. 6279 entries in metadata table. Finished in 1.23s` |
| `logger.warning()` | Non-fatal errors, skipped items | `Page 5 encountered an issue` |

## Console and File Output

Each script logs to both **stderr** (console, enabled by default) and a **rotating log file** under `logs/`:

```python
from loguru import logger
from config import LOGS

logger.add(LOGS / 'page_gathering.log', rotation='5 MB')
```

The `rotation='5 MB'` parameter creates a new log file when the current one exceeds 5 MB, keeping older files alongside.

## Log Files by Stage

| Stage | Log File |
|---|---|
| `fetch-pages` | `logs/page_gathering.log` |
| `extract-metadata` | `logs/process_pages.log` |
| `compute-embeddings` | `logs/embeddings.log` |

The `fetch-details` and `download-images` stages use `print()` for progress output (percentage counters) since they update a single line in-place.

## Example Output

```
2026-07-07 12:22:56.205 | INFO     | __main__:main:77 - Processing page 1...
2026-07-07 12:22:56.206 | INFO     | __main__:fetch_page:57 - Fetching https://windows10spotlight.com...
2026-07-07 12:22:56.450 | SUCCESS  | __main__:fetch_page:64 - Fetching https://windows10spotlight.com DONE.
2026-07-07 12:22:56.451 | SUCCESS  | __main__:main:83 - Processing page 1 DONE.
2026-07-07 12:23:01.120 | SUCCESS  | __main__:main:97 - Finished in 4.92s
```

Each log line includes:

- **Timestamp** with millisecond precision
- **Level** — color-coded in terminal
- **Module:function:line** — exact source location
- **Message** — the log content
