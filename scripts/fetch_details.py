import duckdb
from config import metadata, SPOTLIGHT_REPO, HEADERS
from lxml import html
import asyncio
import aiohttp
from time import perf_counter



con = duckdb.connect(metadata)

def make_url(id):
    """Build the detail page URL for a given entry ID.

    Args:
        id: The entry identifier.

    Returns:
        The full URL string.
    """
    return f"https://{SPOTLIGHT_REPO}/images/{id}"

async def fetch_page(session: aiohttp.ClientSession, id: str, sem: asyncio.Semaphore) -> tuple[str, str]:
    """Fetch the detail page for an entry, respecting a concurrency semaphore.

    Args:
        session: The aiohttp client session.
        id: The entry identifier.
        sem: Semaphore to limit concurrent requests.

    Returns:
        A tuple of (id, page HTML).

    Raises:
        aiohttp.ClientResponseError: If the HTTP request fails.
    """
    async with sem:
        target_url = make_url(id=id)
        async with session.get(url=target_url) as response:
            response.raise_for_status()
            page = await response.text()
            return id, page

def pair_image_to_sha256(nodes):
    """Pair image URLs with their SHA-256 hashes from adjacent HTML nodes.

    Args:
        nodes: A list of lxml elements (anchor and pre tags).

    Returns:
        A list of dicts, each with 'url' and 'sha256' keys.
    """
    pairs = []
    last_img = None

    for node in nodes:
        if node.tag == "a":
            if last_img is not None:
                pairs.append(last_img)
            last_img = {
                "url": node.get("href"),
                "sha256": None,
            }
        elif node.tag == "pre" and last_img is not None:
            meta = dict(
                line.split(": ", 1)
                for line in node.text.strip().splitlines()
                if ": " in line
            )
            last_img["sha256"] = meta.get("sha256")
            pairs.append(last_img)
            last_img = None

    if last_img is not None:
        pairs.append(last_img)
    return pairs

def insert_title_date(id, title, date):
    """Update the title and date for a metadata entry.

    Args:
        id: The entry identifier.
        title: The entry title.
        date: The entry date.
    """
    con.execute(
        "UPDATE metadata SET title=?, date=? WHERE id=?",
        [title, date, id]
    )

def insert_pairs(id, pairs):
    """Insert image URL and SHA-256 pairs into the images table.

    Args:
        id: The parent metadata entry identifier.
        pairs: A list of dicts with 'url' and 'sha256' keys.
    """
    con.executemany(
        "INSERT INTO images (id_meta, url, sha256) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
        [(id, p['url'], p['sha256']) for p in pairs]
    )

def insert_tags(id, tags):
    """Insert tags associated with a metadata entry.

    Args:
        id: The parent metadata entry identifier.
        tags: A list of lxml elements whose text content are tag names.
    """
    con.executemany(
        "INSERT INTO image_tag (id_meta, tag) VALUES (?, ?) ON CONFLICT DO NOTHING",
        [(id, tag.text_content()) for tag in tags]
    )

def extract_info(html_, id):
    """Extract title, date, tags, and image pairs from a detail page.

    Args:
        html_: Raw HTML string of the detail page.
        id: The entry identifier.

    Returns:
        A dict with 'title', 'date', 'tags', and 'imgs' keys.
    """
    tree = html.fromstring(html_)
    article = tree.xpath('//main//article')[0]

    title = article.xpath('.//h1')[0].text_content()
    date  = article.xpath('.//aside[@class="meta"]//span[@class="date"]')[0].text_content()
    entry = article.xpath('.//div[@class="entry"]')[0]
    tags  = article.xpath('.//aside[a]/a')
    nodes = entry.xpath('.//a[img] | .//pre')
    pairs = pair_image_to_sha256(nodes)

    return {
        'title': title,
        'date':  date,
        'tags':  tags,
        'imgs':  pairs
    }

def process_result(id, page, counter, total):
    """Parse a fetched detail page and persist its data to the database.

    Args:
        id: The entry identifier.
        page: Raw HTML string of the detail page.
        counter: A single-element list used as a mutable counter.
        total: Total number of entries to process (for progress display).
    """
    counter[0] += 1
    print(f"\r{100 * counter[0] / total:.2f} %\033[0K", end="", flush=True)
    info = extract_info(page, id)
    insert_title_date(id=id, title=info['title'], date=info['date'])
    insert_pairs(id=id, pairs=info['imgs'])
    insert_tags(id=id, tags=info['tags'])

async def main():
    start = perf_counter()
    SEM = 20
    ids = [row[0] for row in con.execute("SELECT id FROM metadata").fetchall()]
    sem = asyncio.Semaphore(SEM)
    counter = [0]

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_page(session, id, sem) for id in ids]

        for coro in asyncio.as_completed(tasks):
            try:
                id, page = await coro
                process_result(id, page, counter, len(ids))
            except Exception as e:
                print(f"\nFailed: {e}")

        con.commit()
        elapsed = perf_counter() - start
        print(f"\nFinished in {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())