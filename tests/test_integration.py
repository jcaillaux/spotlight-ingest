import duckdb
import pytest
from pathlib import Path
from PIL import Image


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    id VARCHAR PRIMARY KEY,
    date TIMESTAMP,
    title VARCHAR
);

CREATE TABLE IF NOT EXISTS images (
    id_meta VARCHAR REFERENCES metadata(id),
    url VARCHAR UNIQUE,
    sha256 VARCHAR,
    path VARCHAR,
    width INTEGER,
    height INTEGER,
    PRIMARY KEY (id_meta, url)
);

CREATE TABLE IF NOT EXISTS image_tag (
    id_meta VARCHAR REFERENCES metadata(id),
    tag VARCHAR,
    PRIMARY KEY (id_meta, tag)
);

CREATE TABLE IF NOT EXISTS embeddings (
    url VARCHAR PRIMARY KEY REFERENCES images(url),
    embedding FLOAT[512]
);
"""


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

class TestInitDb:

    def test_creates_all_four_tables(self, tmp_path):
        """All four expected tables are created."""
        con = duckdb.connect(str(tmp_path / "test.db"))
        con.sql(CREATE_TABLES_SQL)
        tables = [
            row[0] for row in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
        ]
        assert tables == ["embeddings", "image_tag", "images", "metadata"]
        con.close()

    def test_no_extra_tables_created(self, tmp_path):
        """Exactly four tables are created, no more."""
        con = duckdb.connect(str(tmp_path / "test.db"))
        con.sql(CREATE_TABLES_SQL)
        count = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchone()[0]
        assert count == 4
        con.close()

    def test_idempotent_creation(self, tmp_path):
        """Running the schema SQL twice does not raise."""
        con = duckdb.connect(str(tmp_path / "test.db"))
        con.sql(CREATE_TABLES_SQL)
        con.sql(CREATE_TABLES_SQL)
        count = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchone()[0]
        assert count == 4
        con.close()

    def test_metadata_table_starts_empty(self, tmp_path):
        """Tables start with zero rows."""
        con = duckdb.connect(str(tmp_path / "test.db"))
        con.sql(CREATE_TABLES_SQL)
        count = con.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        assert count == 0
        con.close()


# ---------------------------------------------------------------------------
# process_pages.parse_html
# ---------------------------------------------------------------------------

SPOTLIGHT_PAGE_HTML = """
<html>
<body>
<main>
    <a class="anons-thumbnail show" href="https://example.com/images/first-id/">
        <img src="thumb1.jpg">
    </a>
    <a class="anons-thumbnail show" href="https://example.com/images/second-id/">
        <img src="thumb2.jpg">
    </a>
    <a class="other-class" href="https://example.com/images/ignored/">
        <img src="thumb3.jpg">
    </a>
</main>
</body>
</html>
"""


class TestParseHtml:

    def test_extracts_matching_ids(self, tmp_path):
        """Extracts IDs from links with the correct class."""
        from scripts.process_pages import parse_html
        html_file = tmp_path / "page.html"
        html_file.write_text(SPOTLIGHT_PAGE_HTML)
        ids = parse_html(html_file)
        assert "first-id" in ids

    def test_extracts_all_matching_ids(self, tmp_path):
        """All matching links are captured."""
        from scripts.process_pages import parse_html
        html_file = tmp_path / "page.html"
        html_file.write_text(SPOTLIGHT_PAGE_HTML)
        ids = parse_html(html_file)
        assert len(ids) == 2

    def test_ignores_wrong_class(self, tmp_path):
        """Links with a different class are not included."""
        from scripts.process_pages import parse_html
        html_file = tmp_path / "page.html"
        html_file.write_text(SPOTLIGHT_PAGE_HTML)
        ids = parse_html(html_file)
        assert "ignored" not in ids

    def test_empty_page_returns_empty(self, tmp_path):
        """A page with no matching links returns an empty list."""
        from scripts.process_pages import parse_html
        html_file = tmp_path / "empty.html"
        html_file.write_text("<html><body><main></main></body></html>")
        ids = parse_html(html_file)
        assert ids == []


# ---------------------------------------------------------------------------
# fetch_details.extract_info
# ---------------------------------------------------------------------------

DETAIL_PAGE_HTML = """
<html>
<body>
<main>
<article>
    <h1>Test Title</h1>
    <aside class="meta">
        <span class="date">2024-01-01</span>
    </aside>
    <div class="entry">
        <a href="https://example.com/img1.jpg"><img src="thumb1.jpg"></a>
        <pre>sha256: abc123</pre>
        <a href="https://example.com/img2.jpg"><img src="thumb2.jpg"></a>
        <pre>sha256: def456</pre>
    </div>
    <aside>
        <a>tag1</a>
        <a>tag2</a>
    </aside>
</article>
</main>
</body>
</html>
"""


class TestExtractInfo:

    def test_extracts_title(self):
        """The title is correctly extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["title"] == "Test Title"

    def test_title_is_not_empty(self):
        """The title is not an empty string."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["title"] != ""

    def test_extracts_date(self):
        """The date is correctly extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["date"] == "2024-01-01"

    def test_extracts_correct_tag_count(self):
        """The expected number of tags is extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert len(result["tags"]) == 2

    def test_extracts_correct_image_count(self):
        """The expected number of image pairs is extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert len(result["imgs"]) == 2

    def test_first_image_url(self):
        """The first image URL is correctly extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["imgs"][0]["url"] == "https://example.com/img1.jpg"

    def test_first_image_sha256(self):
        """The first image sha256 is correctly extracted."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["imgs"][0]["sha256"] == "abc123"

    def test_second_image_sha256_differs_from_first(self):
        """Each image has its own distinct sha256."""
        from scripts.fetch_details import extract_info
        result = extract_info(DETAIL_PAGE_HTML, "test-id")
        assert result["imgs"][0]["sha256"] != result["imgs"][1]["sha256"]


# ---------------------------------------------------------------------------
# Database insert and query
# ---------------------------------------------------------------------------

class TestDatabaseOperations:

    @pytest.fixture()
    def db(self):
        """Provides an in-memory DuckDB connection with the full schema."""
        con = duckdb.connect(":memory:")
        con.sql(CREATE_TABLES_SQL)
        yield con
        con.close()

    def test_insert_metadata(self, db):
        """A metadata row can be inserted and queried back."""
        db.execute("INSERT INTO metadata (id, title) VALUES (?, ?)", ["id-1", "Title"])
        row = db.execute("SELECT title FROM metadata WHERE id = ?", ["id-1"]).fetchone()
        assert row[0] == "Title"

    def test_metadata_primary_key_enforced(self, db):
        """Duplicate metadata IDs are rejected."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        with pytest.raises(duckdb.ConstraintException):
            db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])

    def test_insert_images_for_metadata(self, db):
        """Image rows referencing a metadata entry can be inserted."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        db.execute(
            "INSERT INTO images (id_meta, url, sha256) VALUES (?, ?, ?)",
            ["id-1", "https://example.com/img.jpg", "aaa"],
        )
        count = db.execute("SELECT COUNT(*) FROM images WHERE id_meta = ?", ["id-1"]).fetchone()[0]
        assert count == 1

    def test_images_foreign_key_enforced(self, db):
        """Inserting an image with a non-existent metadata ID is rejected."""
        with pytest.raises(duckdb.ConstraintException):
            db.execute(
                "INSERT INTO images (id_meta, url) VALUES (?, ?)",
                ["nonexistent", "https://example.com/img.jpg"],
            )

    def test_image_url_uniqueness(self, db):
        """The same URL cannot appear twice in the images table."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        db.execute(
            "INSERT INTO images (id_meta, url) VALUES (?, ?)",
            ["id-1", "https://example.com/img.jpg"],
        )
        with pytest.raises(duckdb.ConstraintException):
            db.execute(
                "INSERT INTO images (id_meta, url) VALUES (?, ?)",
                ["id-1", "https://example.com/img.jpg"],
            )

    def test_insert_tags(self, db):
        """Tags can be inserted and counted."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        db.executemany(
            "INSERT INTO image_tag (id_meta, tag) VALUES (?, ?)",
            [("id-1", "landscape"), ("id-1", "sunset")],
        )
        count = db.execute(
            "SELECT COUNT(*) FROM image_tag WHERE id_meta = ?", ["id-1"]
        ).fetchone()[0]
        assert count == 2

    def test_duplicate_tag_rejected(self, db):
        """The same tag for the same metadata ID is rejected."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        db.execute("INSERT INTO image_tag (id_meta, tag) VALUES (?, ?)", ["id-1", "sunset"])
        with pytest.raises(duckdb.ConstraintException):
            db.execute("INSERT INTO image_tag (id_meta, tag) VALUES (?, ?)", ["id-1", "sunset"])

    def test_metadata_images_join(self, db):
        """Metadata and images can be joined on the foreign key."""
        db.execute("INSERT INTO metadata (id, title) VALUES (?, ?)", ["id-1", "Entry"])
        db.execute(
            "INSERT INTO images (id_meta, url) VALUES (?, ?)",
            ["id-1", "https://example.com/img.jpg"],
        )
        row = db.execute(
            "SELECT m.title, i.url FROM metadata m JOIN images i ON m.id = i.id_meta"
        ).fetchone()
        assert row[0] == "Entry"

    def test_metadata_images_join_no_cross_contamination(self, db):
        """A join does not return images from other metadata entries."""
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-1"])
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["id-2"])
        db.execute("INSERT INTO images (id_meta, url) VALUES (?, ?)", ["id-1", "https://a.jpg"])
        db.execute("INSERT INTO images (id_meta, url) VALUES (?, ?)", ["id-2", "https://b.jpg"])
        rows = db.execute(
            "SELECT i.url FROM metadata m JOIN images i ON m.id = i.id_meta WHERE m.id = ?",
            ["id-1"],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "https://a.jpg"


# ---------------------------------------------------------------------------
# store_image.get_dimensions
# ---------------------------------------------------------------------------

class TestGetDimensions:

    def test_returns_correct_width(self, tmp_path):
        """Width is correctly read from the image."""
        from scripts.store_image import get_dimensions
        img_path = tmp_path / "test.png"
        Image.new("RGB", (100, 200)).save(img_path)
        width, _ = get_dimensions(img_path)
        assert width == 100

    def test_returns_correct_height(self, tmp_path):
        """Height is correctly read from the image."""
        from scripts.store_image import get_dimensions
        img_path = tmp_path / "test.png"
        Image.new("RGB", (100, 200)).save(img_path)
        _, height = get_dimensions(img_path)
        assert height == 200

    def test_width_is_not_height(self, tmp_path):
        """Width and height are not swapped for a non-square image."""
        from scripts.store_image import get_dimensions
        img_path = tmp_path / "test.png"
        Image.new("RGB", (100, 200)).save(img_path)
        width, height = get_dimensions(img_path)
        assert width != height

    def test_square_image(self, tmp_path):
        """Works for a square image."""
        from scripts.store_image import get_dimensions
        img_path = tmp_path / "square.png"
        Image.new("RGB", (50, 50)).save(img_path)
        width, height = get_dimensions(img_path)
        assert width == height == 50

    def test_invalid_file_raises(self, tmp_path):
        """A non-image file raises an exception."""
        from scripts.store_image import get_dimensions
        bad_file = tmp_path / "bad.png"
        bad_file.write_text("not an image")
        with pytest.raises(Exception):
            get_dimensions(bad_file)


# ---------------------------------------------------------------------------
# init_db.main via monkeypatch
# ---------------------------------------------------------------------------

class TestInitDbScript:

    def test_creates_database_file(self, tmp_path, monkeypatch):
        """The init_db script creates the database file."""
        db_path = tmp_path / "metadata.db"
        monkeypatch.setattr("scripts.init_db.metadata", db_path)
        from scripts.init_db import main
        main()
        assert db_path.exists()

    def test_database_file_not_empty(self, tmp_path, monkeypatch):
        """The created database file is not empty."""
        db_path = tmp_path / "metadata.db"
        monkeypatch.setattr("scripts.init_db.metadata", db_path)
        from scripts.init_db import main
        main()
        assert db_path.stat().st_size > 0

    def test_tables_exist_after_init(self, tmp_path, monkeypatch):
        """All four tables exist after running init_db."""
        db_path = tmp_path / "metadata.db"
        monkeypatch.setattr("scripts.init_db.metadata", db_path)
        from scripts.init_db import main
        main()
        con = duckdb.connect(str(db_path))
        tables = [
            row[0] for row in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
        ]
        assert tables == ["embeddings", "image_tag", "images", "metadata"]
        con.close()

    def test_running_twice_does_not_raise(self, tmp_path, monkeypatch):
        """Running init_db twice is idempotent."""
        db_path = tmp_path / "metadata.db"
        monkeypatch.setattr("scripts.init_db.metadata", db_path)
        from scripts.init_db import main
        main()
        main()


# ---------------------------------------------------------------------------
# fetch_details insert functions
# ---------------------------------------------------------------------------

class TestFetchDetailsInserts:

    @pytest.fixture()
    def db(self):
        """Provides an in-memory DuckDB with schema and a metadata entry."""
        con = duckdb.connect(":memory:")
        con.sql(CREATE_TABLES_SQL)
        con.execute("INSERT INTO metadata (id) VALUES (?)", ["test-id"])
        yield con
        con.close()

    def test_insert_title_date_updates_title(self, db, monkeypatch):
        """insert_title_date sets the title on the metadata row."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_title_date
        insert_title_date("test-id", "My Title", "2024-06-15")
        row = db.execute("SELECT title FROM metadata WHERE id = ?", ["test-id"]).fetchone()
        assert row[0] == "My Title"

    def test_insert_title_date_updates_date(self, db, monkeypatch):
        """insert_title_date sets the date on the metadata row."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_title_date
        insert_title_date("test-id", "My Title", "2024-06-15")
        row = db.execute("SELECT date FROM metadata WHERE id = ?", ["test-id"]).fetchone()
        assert row[0] is not None

    def test_insert_title_date_does_not_affect_other_rows(self, db, monkeypatch):
        """insert_title_date does not modify unrelated metadata entries."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_title_date
        db.execute("INSERT INTO metadata (id) VALUES (?)", ["other-id"])
        insert_title_date("test-id", "My Title", "2024-06-15")
        row = db.execute("SELECT title FROM metadata WHERE id = ?", ["other-id"]).fetchone()
        assert row[0] is None

    def test_insert_pairs_adds_images(self, db, monkeypatch):
        """insert_pairs inserts image rows into the images table."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_pairs
        pairs = [{"url": "https://a.jpg", "sha256": "aaa"}]
        insert_pairs("test-id", pairs)
        count = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        assert count == 1

    def test_insert_pairs_stores_sha256(self, db, monkeypatch):
        """insert_pairs stores the sha256 value."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_pairs
        pairs = [{"url": "https://a.jpg", "sha256": "aaa"}]
        insert_pairs("test-id", pairs)
        row = db.execute("SELECT sha256 FROM images WHERE url = ?", ["https://a.jpg"]).fetchone()
        assert row[0] == "aaa"

    def test_insert_pairs_duplicate_ignored(self, db, monkeypatch):
        """Inserting the same pair twice does not raise."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_pairs
        pairs = [{"url": "https://a.jpg", "sha256": "aaa"}]
        insert_pairs("test-id", pairs)
        insert_pairs("test-id", pairs)
        count = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        assert count == 1

    def test_insert_tags_adds_tags(self, db, monkeypatch):
        """insert_tags inserts tag rows."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_tags
        from lxml.html import fromstring
        tags = fromstring("<div><a>landscape</a><a>sunset</a></div>").findall(".//a")
        insert_tags("test-id", tags)
        count = db.execute("SELECT COUNT(*) FROM image_tag WHERE id_meta = ?", ["test-id"]).fetchone()[0]
        assert count == 2

    def test_insert_tags_stores_text(self, db, monkeypatch):
        """insert_tags stores the tag text content."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_tags
        from lxml.html import fromstring
        tags = fromstring("<div><a>landscape</a></div>").findall(".//a")
        insert_tags("test-id", tags)
        row = db.execute("SELECT tag FROM image_tag WHERE id_meta = ?", ["test-id"]).fetchone()
        assert row[0] == "landscape"

    def test_insert_tags_duplicate_ignored(self, db, monkeypatch):
        """Inserting the same tag twice does not raise."""
        monkeypatch.setattr("scripts.fetch_details.con", db)
        from scripts.fetch_details import insert_tags
        from lxml.html import fromstring
        tags = fromstring("<div><a>sunset</a></div>").findall(".//a")
        insert_tags("test-id", tags)
        insert_tags("test-id", tags)
        count = db.execute("SELECT COUNT(*) FROM image_tag").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# store_image.update_image
# ---------------------------------------------------------------------------

class TestUpdateImage:

    @pytest.fixture()
    def db(self):
        """Provides an in-memory DuckDB with a metadata entry and an image row."""
        con = duckdb.connect(":memory:")
        con.sql(CREATE_TABLES_SQL)
        con.execute("INSERT INTO metadata (id) VALUES (?)", ["test-id"])
        con.execute(
            "INSERT INTO images (id_meta, url) VALUES (?, ?)",
            ["test-id", "https://example.com/img.jpg"],
        )
        yield con
        con.close()

    def test_sets_path(self, db, monkeypatch):
        """update_image sets the path column."""
        monkeypatch.setattr("scripts.store_image.con", db)
        from scripts.store_image import update_image
        update_image("https://example.com/img.jpg", "img.jpg", 1920, 1080)
        row = db.execute("SELECT path FROM images WHERE url = ?", ["https://example.com/img.jpg"]).fetchone()
        assert row[0] == "img.jpg"

    def test_sets_width(self, db, monkeypatch):
        """update_image sets the width column."""
        monkeypatch.setattr("scripts.store_image.con", db)
        from scripts.store_image import update_image
        update_image("https://example.com/img.jpg", "img.jpg", 1920, 1080)
        row = db.execute("SELECT width FROM images WHERE url = ?", ["https://example.com/img.jpg"]).fetchone()
        assert row[0] == 1920

    def test_sets_height(self, db, monkeypatch):
        """update_image sets the height column."""
        monkeypatch.setattr("scripts.store_image.con", db)
        from scripts.store_image import update_image
        update_image("https://example.com/img.jpg", "img.jpg", 1920, 1080)
        row = db.execute("SELECT height FROM images WHERE url = ?", ["https://example.com/img.jpg"]).fetchone()
        assert row[0] == 1080

    def test_path_was_null_before(self, db):
        """The path is NULL before update_image is called."""
        row = db.execute("SELECT path FROM images WHERE url = ?", ["https://example.com/img.jpg"]).fetchone()
        assert row[0] is None

    def test_does_not_affect_other_rows(self, db, monkeypatch):
        """update_image does not modify unrelated image rows."""
        monkeypatch.setattr("scripts.store_image.con", db)
        from scripts.store_image import update_image
        db.execute("INSERT INTO images (id_meta, url) VALUES (?, ?)", ["test-id", "https://other.jpg"])
        update_image("https://example.com/img.jpg", "img.jpg", 1920, 1080)
        row = db.execute("SELECT path FROM images WHERE url = ?", ["https://other.jpg"]).fetchone()
        assert row[0] is None


# ---------------------------------------------------------------------------
# compute_embeddings.get_pending_images
# ---------------------------------------------------------------------------

class TestGetPendingImages:

    @pytest.fixture()
    def db(self):
        """Provides an in-memory DuckDB with schema."""
        con = duckdb.connect(":memory:")
        con.sql(CREATE_TABLES_SQL)
        con.execute("INSERT INTO metadata (id) VALUES (?)", ["test-id"])
        yield con
        con.close()

    def test_returns_images_without_embeddings(self, db, monkeypatch):
        """Images with a path but no embedding are returned."""
        monkeypatch.setattr("scripts.compute_embeddings.con", db)
        from scripts.compute_embeddings import get_pending_images
        db.execute(
            "INSERT INTO images (id_meta, url, path) VALUES (?, ?, ?)",
            ["test-id", "https://a.jpg", "a.jpg"],
        )
        rows = get_pending_images()
        assert len(rows) == 1

    def test_excludes_images_with_embeddings(self, db, monkeypatch):
        """Images that already have embeddings are not returned."""
        monkeypatch.setattr("scripts.compute_embeddings.con", db)
        from scripts.compute_embeddings import get_pending_images
        db.execute(
            "INSERT INTO images (id_meta, url, path) VALUES (?, ?, ?)",
            ["test-id", "https://a.jpg", "a.jpg"],
        )
        db.execute(
            "INSERT INTO embeddings (url, embedding) VALUES (?, ?)",
            ["https://a.jpg", [0.0] * 512],
        )
        rows = get_pending_images()
        assert len(rows) == 0

    def test_excludes_images_without_path(self, db, monkeypatch):
        """Images with no local path (not yet downloaded) are excluded."""
        monkeypatch.setattr("scripts.compute_embeddings.con", db)
        from scripts.compute_embeddings import get_pending_images
        db.execute(
            "INSERT INTO images (id_meta, url) VALUES (?, ?)",
            ["test-id", "https://a.jpg"],
        )
        rows = get_pending_images()
        assert len(rows) == 0

    def test_returns_url_and_path(self, db, monkeypatch):
        """Each returned row contains the URL and path."""
        monkeypatch.setattr("scripts.compute_embeddings.con", db)
        from scripts.compute_embeddings import get_pending_images
        db.execute(
            "INSERT INTO images (id_meta, url, path) VALUES (?, ?, ?)",
            ["test-id", "https://a.jpg", "a.jpg"],
        )
        rows = get_pending_images()
        assert rows[0] == ("https://a.jpg", "a.jpg")


# ---------------------------------------------------------------------------
# compute_embeddings.compute_batch (requires model download, slow)
# ---------------------------------------------------------------------------

class TestComputeBatch:

    @pytest.fixture(scope="class")
    def clip(self):
        """Loads the CLIP model once for the whole test class."""
        from scripts.compute_embeddings import load_model
        return load_model()

    def test_returns_numpy_array(self, clip, tmp_path):
        """compute_batch returns a numpy array."""
        import numpy as np
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_path = tmp_path / "test.png"
        Image.new("RGB", (224, 224)).save(img_path)
        result = compute_batch(model, processor, device, [img_path])
        assert isinstance(result, np.ndarray)

    def test_embedding_dimension_is_512(self, clip, tmp_path):
        """Each embedding has 512 dimensions."""
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_path = tmp_path / "test.png"
        Image.new("RGB", (224, 224)).save(img_path)
        result = compute_batch(model, processor, device, [img_path])
        assert result.shape[1] == 512

    def test_single_image_returns_one_row(self, clip, tmp_path):
        """A single image produces a single embedding row."""
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_path = tmp_path / "test.png"
        Image.new("RGB", (224, 224)).save(img_path)
        result = compute_batch(model, processor, device, [img_path])
        assert result.shape[0] == 1

    def test_batch_returns_correct_count(self, clip, tmp_path):
        """A batch of N images produces N embedding rows."""
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        paths = []
        for i in range(3):
            p = tmp_path / f"test_{i}.png"
            Image.new("RGB", (224, 224)).save(p)
            paths.append(p)
        result = compute_batch(model, processor, device, paths)
        assert result.shape[0] == 3

    def test_embeddings_are_normalized(self, clip, tmp_path):
        """Embeddings are L2-normalized (unit vectors)."""
        import numpy as np
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_path = tmp_path / "test.png"
        Image.new("RGB", (224, 224)).save(img_path)
        result = compute_batch(model, processor, device, [img_path])
        norm = np.linalg.norm(result[0])
        assert abs(norm - 1.0) < 1e-5

    def test_embeddings_are_not_all_zero(self, clip, tmp_path):
        """Embeddings contain non-zero values."""
        import numpy as np
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_path = tmp_path / "test.png"
        Image.new("RGB", (224, 224)).save(img_path)
        result = compute_batch(model, processor, device, [img_path])
        assert not np.allclose(result, 0.0)

    def test_different_images_produce_different_embeddings(self, clip, tmp_path):
        """Distinct images produce different embedding vectors."""
        import numpy as np
        from scripts.compute_embeddings import compute_batch
        model, processor, device = clip
        img_a = tmp_path / "a.png"
        img_b = tmp_path / "b.png"
        Image.new("RGB", (224, 224), color="red").save(img_a)
        Image.new("RGB", (224, 224), color="blue").save(img_b)
        result = compute_batch(model, processor, device, [img_a, img_b])
        assert not np.allclose(result[0], result[1])


# ---------------------------------------------------------------------------
# process_pages.main (end-to-end with monkeypatched paths)
# ---------------------------------------------------------------------------

class TestProcessPagesMain:

    def test_inserts_ids_into_db(self, tmp_path, monkeypatch):
        """main() parses HTML files and inserts IDs into the database."""
        from scripts.process_pages import main as pp_main

        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "1.html").write_text("""
        <html><body><main>
            <a class="anons-thumbnail show" href="https://example.com/images/id-one/">
                <img src="t.jpg">
            </a>
        </main></body></html>
        """)

        db_path = tmp_path / "test.db"
        con = duckdb.connect(str(db_path))
        con.sql(CREATE_TABLES_SQL)
        con.close()

        monkeypatch.setattr("scripts.process_pages.DATA", tmp_path)
        monkeypatch.setattr("scripts.process_pages.metadata", db_path)
        pp_main()

        con = duckdb.connect(str(db_path))
        count = con.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        assert count == 1
        con.close()

    def test_does_not_insert_from_wrong_class(self, tmp_path, monkeypatch):
        """main() ignores links with the wrong class."""
        from scripts.process_pages import main as pp_main

        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "1.html").write_text("""
        <html><body><main>
            <a class="other-class" href="https://example.com/images/ignored/">
                <img src="t.jpg">
            </a>
        </main></body></html>
        """)

        db_path = tmp_path / "test.db"
        con = duckdb.connect(str(db_path))
        con.sql(CREATE_TABLES_SQL)
        con.close()

        monkeypatch.setattr("scripts.process_pages.DATA", tmp_path)
        monkeypatch.setattr("scripts.process_pages.metadata", db_path)
        pp_main()

        con = duckdb.connect(str(db_path))
        count = con.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        assert count == 0
        con.close()

    def test_handles_empty_directory(self, tmp_path, monkeypatch):
        """main() handles an empty HTML directory without error."""
        from scripts.process_pages import main as pp_main

        html_dir = tmp_path / "html"
        html_dir.mkdir()

        db_path = tmp_path / "test.db"
        con = duckdb.connect(str(db_path))
        con.sql(CREATE_TABLES_SQL)
        con.close()

        monkeypatch.setattr("scripts.process_pages.DATA", tmp_path)
        monkeypatch.setattr("scripts.process_pages.metadata", db_path)
        pp_main()

        con = duckdb.connect(str(db_path))
        count = con.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        assert count == 0
        con.close()
