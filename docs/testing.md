# Testing

## Running Tests

```bash
make test
```

Or with coverage:

```bash
uv run python -m pytest --cov=scripts --cov=config --cov-report=term-missing tests
```

## Test Philosophy

Tests follow two complementary approaches:

### TAP (Test Anything Protocol)

Each test verifies **one thing**. A single assertion per test makes failures immediately diagnostic — the test name tells you exactly what broke.

```python
def test_paired_sha256_is_correct(self):
    """A paired a+pre produces the correct sha256."""
    ...
    assert result[0]["sha256"] == "abc123"
```

### Tiger Style

Every behavior is tested from **both sides** — what something *is* and what it *is not*. This catches false positives and ensures tests actually exercise the code path they claim to.

```python
def test_extracts_matching_ids(self, tmp_path):
    """Extracts IDs from links with the correct class."""
    ...
    assert "first-id" in ids

def test_ignores_wrong_class(self, tmp_path):
    """Links with a different class are not included."""
    ...
    assert "ignored" not in ids
```

## Test Structure

```
tests/
  test_config.py        # Environment configuration
  test_unit.py          # Pure functions, no I/O
  test_integration.py   # Database, file system, model
```

### Unit Tests (`test_unit.py`)

Test pure functions in isolation — no database, no filesystem, no network.

| Class | Module | Functions Tested |
|---|---|---|
| `TestRepoMakeUrl` | `repo_access` | `make_url` |
| `TestMakeDest` | `repo_access` | `make_dest` |
| `TestExtractPageNumber` | `repo_access` | `extract_page_number` |
| `TestWriteHtml` | `repo_access` | `write_html` |
| `TestLastPageNumber` | `repo_access` | `last_page_number` |
| `TestExtractId` | `process_pages` | `extract_id` |
| `TestReadHtml` | `process_pages` | `read_html` |
| `TestDetailsMakeUrl` | `fetch_details` | `make_url` |
| `TestPairImageToSha256` | `fetch_details` | `pair_image_to_sha256` |
| `TestGetFilename` | `store_image` | `get_filename` |

### Integration Tests (`test_integration.py`)

Test components that interact with DuckDB, the filesystem, or the CLIP model.

| Class | What It Tests |
|---|---|
| `TestInitDb` | Schema creation, idempotency, table count |
| `TestInitDbScript` | `init_db.main()` via monkeypatch |
| `TestParseHtml` | HTML parsing with matching/non-matching classes |
| `TestExtractInfo` | Detail page parsing (title, date, tags, images) |
| `TestDatabaseOperations` | Inserts, constraints, foreign keys, joins |
| `TestFetchDetailsInserts` | `insert_title_date`, `insert_pairs`, `insert_tags` |
| `TestUpdateImage` | `update_image` path/width/height updates |
| `TestGetDimensions` | Image dimension reading, invalid file handling |
| `TestGetPendingImages` | Embedding query filtering logic |
| `TestComputeBatch` | CLIP embedding shape, normalization, distinctness |
| `TestProcessPagesMain` | End-to-end `main()` with monkeypatched paths |

## Coverage

Current coverage sits at **~58%**. The uncovered code is primarily async `main()` functions that perform network I/O — testing those would require mocking `aiohttp` sessions.

| Module | Coverage |
|---|---|
| `config.py` | 100% |
| `init_db.py` | 90% |
| `process_pages.py` | 93% |
| `compute_embeddings.py` | 62% |
| `fetch_details.py` | 61% |
| `repo_access.py` | 46% |
| `store_image.py` | 38% |
