import pytest
from pathlib import Path
from lxml.html import fromstring

from config import DATA, SPOTLIGHT_REPO
from scripts.repo_access import (
    make_url as repo_make_url,
    make_dest,
    extract_page_number,
)
from scripts.process_pages import extract_id
from scripts.fetch_details import (
    make_url as details_make_url,
    pair_image_to_sha256,
)
from scripts.store_image import get_filename


# ---------------------------------------------------------------------------
# repo_access.make_url
# ---------------------------------------------------------------------------

class TestRepoMakeUrl:

    def test_without_page(self):
        """Returns https://{host} when no page is given."""
        assert repo_make_url("example.com") == "https://example.com"

    def test_with_page(self):
        """Returns https://{host}/{page} when a page number is provided."""
        assert repo_make_url("example.com", page=3) == "https://example.com/3"

    def test_with_page_zero(self):
        """Page 0 is a valid value and should appear in the URL."""
        assert repo_make_url("example.com", page=0) == "https://example.com/0"

    def test_page_none_explicitly(self):
        """Explicitly passing None behaves like omitting the argument."""
        assert repo_make_url("example.com", page=None) == "https://example.com"


# ---------------------------------------------------------------------------
# repo_access.make_dest
# ---------------------------------------------------------------------------

class TestMakeDest:

    def test_returns_path_under_data_html(self):
        """Destination lives inside DATA/html/ with an .html suffix."""
        result = make_dest(42)
        assert result == DATA / "html" / "42.html"

    def test_return_type_is_path(self):
        """Return value is a pathlib.Path."""
        assert isinstance(make_dest(1), Path)


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
        """Extracts the maximum numeric page from the second nav element."""
        assert extract_page_number(PAGINATION_HTML) == 7

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
        """Non-numeric path segments are silently skipped."""
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
        """Returns only the last segment regardless of path depth."""
        assert extract_id("https://a.com/x/y/z/my-id/") == "my-id"


# ---------------------------------------------------------------------------
# fetch_details.make_url
# ---------------------------------------------------------------------------

class TestDetailsMakeUrl:

    def test_constructs_image_url(self):
        """Builds the full image detail URL from an id."""
        result = details_make_url("some-image-id")
        assert result == f"https://{SPOTLIGHT_REPO}/images/some-image-id"


# ---------------------------------------------------------------------------
# fetch_details.pair_image_to_sha256
# ---------------------------------------------------------------------------

def _make_nodes(html_fragment):
    """Parse an HTML fragment and return the child elements."""
    tree = fromstring(f"<div>{html_fragment}</div>")
    return list(tree)


class TestPairImageToSha256:

    def test_normal_pairing(self):
        """An a tag followed by a pre tag produces a pair with sha256."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="thumb.jpg"></a>'
            "<pre>sha256: abc123\nsize: 1024</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert len(result) == 1
        assert result[0]["url"] == "https://img.example.com/photo.jpg"
        assert result[0]["sha256"] == "abc123"

    def test_image_without_sha256(self):
        """An a tag not followed by a pre tag yields sha256=None."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/photo.jpg"><img src="thumb.jpg"></a>'
            '<a href="https://img.example.com/other.jpg"><img src="thumb2.jpg"></a>'
        )
        result = pair_image_to_sha256(nodes)
        assert len(result) == 2
        assert result[0]["sha256"] is None
        assert result[1]["sha256"] is None

    def test_empty_list(self):
        """An empty node list returns an empty list."""
        assert pair_image_to_sha256([]) == []

    def test_multiple_pairs(self):
        """Multiple alternating a/pre pairs are all captured."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/a.jpg"><img src="a.jpg"></a>'
            "<pre>sha256: aaa</pre>"
            '<a href="https://img.example.com/b.jpg"><img src="b.jpg"></a>'
            "<pre>sha256: bbb</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert len(result) == 2
        assert result[0]["sha256"] == "aaa"
        assert result[1]["sha256"] == "bbb"

    def test_mixed_paired_and_unpaired(self):
        """An unpaired a tag followed by a paired a+pre tag are both captured."""
        nodes = _make_nodes(
            '<a href="https://img.example.com/orphan.jpg"><img src="o.jpg"></a>'
            '<a href="https://img.example.com/paired.jpg"><img src="p.jpg"></a>'
            "<pre>sha256: ppp</pre>"
        )
        result = pair_image_to_sha256(nodes)
        assert len(result) == 2
        assert result[0]["url"] == "https://img.example.com/orphan.jpg"
        assert result[0]["sha256"] is None
        assert result[1]["url"] == "https://img.example.com/paired.jpg"
        assert result[1]["sha256"] == "ppp"


# ---------------------------------------------------------------------------
# store_image.get_filename
# ---------------------------------------------------------------------------

class TestGetFilename:

    def test_simple_url(self):
        """Extracts the filename from a straightforward URL."""
        assert get_filename("https://example.com/path/to/image.jpg") == "image.jpg"

    def test_url_with_query_string(self):
        """Query parameters are stripped, only the path filename is returned."""
        assert get_filename("https://example.com/img/photo.png?v=2") == "photo.png"

    def test_nested_path(self):
        """Works with deeply nested paths."""
        assert get_filename("https://cdn.example.com/a/b/c/d/file.webp") == "file.webp"
