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


def test_init_db(tmp_path):
    """Verify that the database schema creates all four expected tables.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    db_path = tmp_path / "test.db"
    con = duckdb.connect(str(db_path))
    con.sql(CREATE_TABLES_SQL)

    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    table_names = [row[0] for row in tables]

    assert table_names == ["embeddings", "image_tag", "images", "metadata"]
    con.close()


def test_process_pages_parse_html(tmp_path):
    """Verify that parse_html extracts entry IDs from spotlight page HTML.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    from scripts.process_pages import parse_html

    html_content = """
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
    html_file = tmp_path / "page.html"
    html_file.write_text(html_content)

    ids = parse_html(html_file)

    assert ids == ["first-id", "second-id"]


def test_extract_info():
    """Verify that extract_info parses title, date, tags, and image pairs.

    Tests that the function correctly extracts structured data from an HTML
    string matching the expected spotlight article layout.
    """
    from scripts.fetch_details import extract_info

    html_string = """
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

    result = extract_info(html_string, "test-id")

    assert result["title"] == "Test Title"
    assert result["date"] == "2024-01-01"
    assert len(result["tags"]) == 2
    assert len(result["imgs"]) == 2
    assert result["imgs"][0]["url"] == "https://example.com/img1.jpg"
    assert result["imgs"][0]["sha256"] == "abc123"
    assert result["imgs"][1]["url"] == "https://example.com/img2.jpg"
    assert result["imgs"][1]["sha256"] == "def456"


def test_insert_and_query_metadata():
    """Verify inserting and querying metadata, images, and tags in DuckDB.

    Creates an in-memory database with the full schema, inserts sample data
    across all related tables, and confirms correct counts and values.
    """
    con = duckdb.connect(":memory:")
    con.sql(CREATE_TABLES_SQL)

    con.execute(
        "INSERT INTO metadata (id, date, title) VALUES (?, ?, ?)",
        ["test-id", "2024-01-15", "Test Entry"],
    )

    con.executemany(
        "INSERT INTO images (id_meta, url, sha256) VALUES (?, ?, ?)",
        [
            ("test-id", "https://example.com/img1.jpg", "aaa111"),
            ("test-id", "https://example.com/img2.jpg", "bbb222"),
        ],
    )

    con.executemany(
        "INSERT INTO image_tag (id_meta, tag) VALUES (?, ?)",
        [("test-id", "landscape"), ("test-id", "sunset")],
    )

    # Verify metadata
    row = con.execute("SELECT id, title FROM metadata WHERE id = ?", ["test-id"]).fetchone()
    assert row == ("test-id", "Test Entry")

    # Verify image count
    img_count = con.execute(
        "SELECT COUNT(*) FROM images WHERE id_meta = ?", ["test-id"]
    ).fetchone()[0]
    assert img_count == 2

    # Verify tag count
    tag_count = con.execute(
        "SELECT COUNT(*) FROM image_tag WHERE id_meta = ?", ["test-id"]
    ).fetchone()[0]
    assert tag_count == 2

    # Verify join between metadata and images
    joined = con.execute(
        "SELECT m.title, i.url FROM metadata m "
        "JOIN images i ON m.id = i.id_meta ORDER BY i.url"
    ).fetchall()
    assert len(joined) == 2
    assert joined[0] == ("Test Entry", "https://example.com/img1.jpg")

    con.close()


def test_get_dimensions(tmp_path):
    """Verify that get_dimensions returns the correct width and height.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    from scripts.store_image import get_dimensions

    img_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (100, 200), color="red")
    img.save(img_path)

    width, height = get_dimensions(img_path)

    assert width == 100
    assert height == 200
