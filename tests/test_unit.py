import pytest
from pathlib import Path
from lxml.html import fromstring

from config import DATA, SPOTLIGHT_REPO
from scripts.repo_access import (
    make_url as repo_make_url,
    make_dest,
    extract_page_number,
    write_html,
    last_page_number,
)
from scripts.process_pages import extract_id, read_html
from scripts.fetch_details import (
    make_url as details_make_url,
    pair_image_to_sha256,
)
from scripts.store_image import get_filename


# ---------------------------------------------------------------------------
# repo_access.make_url
# ---------------------------------------------------------------------------

class TestRepoMakeUrl:

    def test_without_page_returns_host_url(self):
        """Returns the base URL when no page is given."""
        assert repo_make_url("example.com") == "https://example.com"

    def test_without_page_does_not_contain_slash_suffix(self):
        """Base URL has no trailing slash or page segment."""
        result = repo_make_url("example.com")
        assert result.count("/") == 2

    def test_with_page_appends_page_number(self):
        """Appends the page number as a path segment."""
        assert repo_make_url("example.com", page=3) == "https://example.com/3"

    def test_with_page_does_not_equal_base_url(self):
        """A paged URL differs from the base URL."""
        assert repo_make_url("example.com", page=3) != repo_make_url("example.com")

    def test_with_page_zero_includes_zero(self):
        """Page 0 is a valid value and appears in the URL."""
        assert repo_make_url("example.com", page=0) == "https://example.com/0"

    def test_page_none_is_same_as_no_page(self):
        """Explicitly passing None behaves like omitting the argument."""
        assert repo_make_url("example.com", page=None) == repo_make_url("example.com")

    def test_different_hosts_produce_different_urls(self):
        """Different hosts produce different base URLs."""
        assert repo_make_url("a.com") != repo_make_url("b.com")


# ---------------------------------------------------------------------------
# repo_access.make_dest
# ---------------------------------------------------------------------------

class TestMakeDest:

    def test_returns_path_under_data_html(self):
        """Destination lives inside DATA/html/."""
        result = make_dest(42)
        assert result.parent == DATA / "html"

    def test_filename_matches_page_number(self):
        """Filename is the page number with .html extension."""
        result = make_dest(42)
        assert result.name == "42.html"

    def test_return_type_is_path(self):
        """Return value is a pathlib.Path."""
        assert isinstance(make_dest(1), Path)

    def test_different_pages_produce_different_paths(self):
        """Different page numbers produce different file paths."""
        assert make_dest(1) != make_dest(2)


# ---------------------------------------------------------------------------
# repo_access.extract_page_number
# ---------------------------------------------------------------------------

PAGINATION_HTML = """
<html>
<body>
  <nav>
    <a href="/category/first">First</a>
  </nav>
  <nav>
    <a href="/page/1/">1</a>
    <a href="/page/2/">2</a>
    <a href="/page/7/">7</a>
    <a href="/page/3/">3</a>
  </nav>
</body>
</html>
"""


class TestExtractPageNumber:

    def test_returns_max_page(self):
        """Extracts the maximum numeric page from the second nav."""
        assert extract_page_number(PAGINATION_HTML) == 7

    def test_does_not_return_non_max_page(self):
        """Does not return a non-maximum page number."""
        assert extract_page_number(PAGINATION_HTML) != 3

    def test_single_page_link(self):
        """Works when only one page link exists."""
        html = """
        <html><body>
          <nav><a href="/x">X</a></nav>
          <nav><a href="/page/5/">5</a></nav>
        </body></html>
        """
        assert extract_page_number(html) == 5

    def test_non_numeric_links_ignored(self):
        """Non-numeric path segments are skipped."""
        html = """
        <html><body>
          <nav><a href="/x">X</a></nav>
          <nav>
            <a href="/page/next/">next</a>
            <a href="/page/4/">4</a>
          </nav>
        </body></html>
        """
        assert extract_page_number(html) == 4

    def test_wrong_nav_count_raises(self):
        """Raises AssertionError when there are not exactly 2 nav elements."""
        html = "<html><body><nav><a href='/1/'>1</a></nav></body></html>"
        with pytest.raises(AssertionError):
            extract_page_number(html)

    def test_no_numeric_links_raises(self):
        """Raises ValueError when no numeric page links exist."""
        html = """
        <html><body>
          <nav><a href="/x">X</a></nav>
          <nav><a href="/page/next/">next</a></nav>
        </body></html>
        """
        with pytest.raises(ValueError):
            extract_page_number(html)


# ---------------------------------------------------------------------------
# process_pages.extract_id
# ---------------------------------------------------------------------------

class TestExtractId:

    def test_trailing_slash(self):
        """Strips trailing slash and returns the last path segment."""
        assert extract_id("https://example.com/images/foo-bar/") == "foo-bar"

    def test_no_trailing_slash(self):
        """Works without a trailing slash."""
        assert extract_id("https://example.com/images/foo-bar") == "foo-bar"

    def test_deeply_nested_path(self):
        """Returns only the last segment regardless of depth."""
        assert extract_id("https://a.com/x/y/z/my-id/") == "my-id"

    def test_does_not_return_parent_segment(self):
        """Does not return an intermediate path segment."""
        assert extract_id("https://a.com/images/my-id/") != "images"

    def test_single_segment(self):
        """Works with a single path segment."""
        assert extract_id("my-id") == "my-id"

    def test_single_segment_with_trailing_slash(self):
        """Handles a bare segment with trailing slash."""
        assert extract_id("my-id/") == "my-id"


# ---------------------------------------------------------------------------
# fetch_details.make_url
# ---------------------------------------------------------------------------

class TestDetailsMakeUrl:

    def test_constructs_image_url(self):
        """Builds the full image detail URL from an id."""
        result = details_make_url("some-image-id")
        assert result == f"https://{SPOTLIGHT_REPO}/images/some-image-id"

    def test_contains_id_in_path(self):
        """The id appears in the URL path."""
        assert "some-image-id" in details_make_url("some-image-id")

    def test_different_ids_produce_different_urls(self):
        """Different IDs produce different URLs."""
        assert details_make_url("id-a") != details_make_url("id-b")


# ---------------------------------------------------------------------------
# fetch_details.pair_image_to_sha256
# ---------------------------------------------------------------------------

def _make_nodes(html_fragment):
    """Parse an HTML fragment and return the child elements."""
    tree = fromstring(f"<div>{html_fragment}</div>")
    return list(tree)


class TestPairImageToSha256:

    def test_paired_url_is_correct(self):
        """A paired a+pre produces the correct URL."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="t.jpg"></a>'
            "<pre>sha256: abc123</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert result[0]["url"] == "https://img.example.com/photo.jpg"

    def test_paired_sha256_is_correct(self):
        """A paired a+pre produces the correct sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="t.jpg"></a>'
            "<pre>sha256: abc123</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert result[0]["sha256"] == "abc123"

    def test_paired_sha256_is_not_none(self):
        """A paired a+pre does not have a None sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="t.jpg"></a>'
            "<pre>sha256: abc123</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert result[0]["sha256"] is not None

    def test_unpaired_image_has_none_sha256(self):
        """An a tag not followed by a pre tag yields sha256=None."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="t.jpg"></a>'
            '<a href="https://img.example.com/other.jpg"><img src="t2.jpg"></a>'
        )
        result = pair_image_to_sha256(nodes)
        assert result[0]["sha256"] is None

    def test_unpaired_image_still_has_url(self):
        """An unpaired image still captures its URL."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="t.jpg"></a>'
            '<a href="https://img.example.com/other.jpg"><img src="t2.jpg"></a>'
        )
        result = pair_image_to_sha256(nodes)
        assert result[0]["url"] == "https://img.example.com/photo.jpg"

    def test_empty_list_returns_empty(self):
        """An empty node list returns an empty list."""
        assert pair_image_to_sha256([]) == []

    def test_empty_list_does_not_return_none(self):
        """An empty node list returns a list, not None."""
        assert pair_image_to_sha256([]) is not None

    def test_multiple_pairs_count(self):
        """Multiple alternating a/pre pairs are all captured."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/a.jpg"><img src="a.jpg"></a>'
            "<pre>sha256: aaa</pre>"
            '<a href="https://img.example.com/b.jpg"><img src="b.jpg"></a>'
            "<pre>sha256: bbb</pre>"
        )
        assert len(pair_image_to_sha256(nodes)) == 2

    def test_multiple_pairs_first_sha256(self):
        """First pair in a sequence gets the correct sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/a.jpg"><img src="a.jpg"></a>'
            "<pre>sha256: aaa</pre>"
            '<a href="https://img.example.com/b.jpg"><img src="b.jpg"></a>'
            "<pre>sha256: bbb</pre>"
        )
        assert pair_image_to_sha256(nodes)[0]["sha256"] == "aaa"

    def test_multiple_pairs_second_sha256(self):
        """Second pair in a sequence gets the correct sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/a.jpg"><img src="a.jpg"></a>'
            "<pre>sha256: aaa</pre>"
            '<a href="https://img.example.com/b.jpg"><img src="b.jpg"></a>'
            "<pre>sha256: bbb</pre>"
        )
        assert pair_image_to_sha256(nodes)[1]["sha256"] == "bbb"

    def test_mixed_orphan_is_none(self):
        """In a mixed sequence, the orphan a tag gets sha256=None."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/orphan.jpg"><img src="o.jpg"></a>'
            '<a href="https://img.example.com/paired.jpg"><img src="p.jpg"></a>'
            "<pre>sha256: ppp</pre>"
        )
        assert pair_image_to_sha256(nodes)[0]["sha256"] is None

    def test_mixed_paired_is_not_none(self):
        """In a mixed sequence, the paired a tag gets a sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/orphan.jpg"><img src="o.jpg"></a>'
            '<a href="https://img.example.com/paired.jpg"><img src="p.jpg"></a>'
            "<pre>sha256: ppp</pre>"
        )
        assert pair_image_to_sha256(nodes)[1]["sha256"] is not None


# ---------------------------------------------------------------------------
# store_image.get_filename
# ---------------------------------------------------------------------------

class TestGetFilename:

    def test_simple_url(self):
        """Extracts the filename from a straightforward URL."""
        assert get_filename("https://example.com/path/to/image.jpg") == "image.jpg"

    def test_does_not_include_path(self):
        """Does not include any path component in the result."""
        assert "/" not in get_filename("https://example.com/path/to/image.jpg")

    def test_url_with_query_string(self):
        """Query parameters are stripped."""
        assert get_filename("https://example.com/img/photo.png?v=2") == "photo.png"

    def test_query_string_not_in_result(self):
        """Query string characters do not appear in the filename."""
        assert "?" not in get_filename("https://example.com/img/photo.png?v=2")

    def test_nested_path(self):
        """Works with deeply nested paths."""
        assert get_filename("https://cdn.example.com/a/b/c/d/file.webp") == "file.webp"

    def test_preserves_extension(self):
        """The file extension is preserved."""
        result = get_filename("https://example.com/image.jpg")
        assert result.endswith(".jpg")


# ---------------------------------------------------------------------------
# repo_access.write_html
# ---------------------------------------------------------------------------

class TestWriteHtml:

    def test_writes_content_to_file(self, tmp_path):
        """The HTML content is written to the destination file."""
        dest = tmp_path / "page.html"
        write_html("<html>hello</html>", dest)
        assert dest.read_text() == "<html>hello</html>"

    def test_file_exists_after_write(self, tmp_path):
        """The destination file exists after writing."""
        dest = tmp_path / "page.html"
        write_html("<html></html>", dest)
        assert dest.exists()

    def test_file_does_not_exist_before_write(self, tmp_path):
        """The destination file does not exist before writing."""
        dest = tmp_path / "page.html"
        assert not dest.exists()

    def test_overwrites_existing_file(self, tmp_path):
        """Writing to an existing file replaces its content."""
        dest = tmp_path / "page.html"
        write_html("old", dest)
        write_html("new", dest)
        assert dest.read_text() == "new"

    def test_overwritten_content_is_not_old(self, tmp_path):
        """After overwrite, old content is gone."""
        dest = tmp_path / "page.html"
        write_html("old", dest)
        write_html("new", dest)
        assert dest.read_text() != "old"


# ---------------------------------------------------------------------------
# repo_access.last_page_number
# ---------------------------------------------------------------------------

class TestLastPageNumber:

    def test_returns_max_page(self, tmp_path, monkeypatch):
        """Returns the highest numbered HTML file."""
        monkeypatch.setattr("scripts.repo_access.DATA", tmp_path)
        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "1.html").touch()
        (html_dir / "5.html").touch()
        (html_dir / "3.html").touch()
        assert last_page_number() == 5

    def test_does_not_return_non_max(self, tmp_path, monkeypatch):
        """Does not return a non-maximum page number."""
        monkeypatch.setattr("scripts.repo_access.DATA", tmp_path)
        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "1.html").touch()
        (html_dir / "5.html").touch()
        assert last_page_number() != 1

    def test_empty_directory_returns_zero(self, tmp_path, monkeypatch):
        """Returns 0 when no HTML files exist."""
        monkeypatch.setattr("scripts.repo_access.DATA", tmp_path)
        html_dir = tmp_path / "html"
        html_dir.mkdir()
        assert last_page_number() == 0

    def test_single_file(self, tmp_path, monkeypatch):
        """Works with a single HTML file."""
        monkeypatch.setattr("scripts.repo_access.DATA", tmp_path)
        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "42.html").touch()
        assert last_page_number() == 42


# ---------------------------------------------------------------------------
# process_pages.read_html
# ---------------------------------------------------------------------------

class TestReadHtml:

    def test_reads_file_content(self, tmp_path):
        """Returns the full text content of the file."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html>content</html>")
        assert read_html(html_file) == "<html>content</html>"

    def test_returns_string(self, tmp_path):
        """Return type is a string."""
        html_file = tmp_path / "test.html"
        html_file.write_text("")
        assert isinstance(read_html(html_file), str)

    def test_empty_file_returns_empty_string(self, tmp_path):
        """An empty file returns an empty string."""
        html_file = tmp_path / "test.html"
        html_file.write_text("")
        assert read_html(html_file) == ""

    def test_empty_file_does_not_return_none(self, tmp_path):
        """An empty file does not return None."""
        html_file = tmp_path / "test.html"
        html_file.write_text("")
        assert read_html(html_file) is not None
