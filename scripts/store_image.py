import duckdb
import asyncio
import aiohttp
from time import perf_counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from PIL import Image
from config import metadata, IMG, HEADERS

con = duckdb.connect(metadata)

def get_filename(url: str) -> str:
    return PurePosixPath(urlparse(url).path).name

async def download_image(session: aiohttp.ClientSession, url: str, sem: asyncio.Semaphore) -> tuple[str, Path]:
    async with sem:
        dest = IMG / get_filename(url)
        async with session.get(url) as response:
            response.raise_for_status()
            with open(dest, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
        return url, dest

def get_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size  # (width, height)

def update_image(url: str, path: str, width: int, height: int):
    con.execute(
        "UPDATE images SET path=?, width=?, height=? WHERE url=?",
        [path, width, height, url]
    )

async def main():
    start = perf_counter()
    SEM = 20
    IMG.mkdir(parents=True, exist_ok=True)

    rows = con.execute("SELECT url FROM images WHERE path IS NULL").fetchall()
    urls = [row[0] for row in rows]
    sem = asyncio.Semaphore(SEM)
    count = 0
    total = len(urls)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [download_image(session, url, sem) for url in urls]

        for coro in asyncio.as_completed(tasks):
            try:
                url, dest = await coro
                width, height = get_dimensions(dest)
                update_image(url, dest.name, width, height)
            except Exception as e:
                print(f"\nFailed: {e}")

            count += 1
            print(f"\r{100 * count / total:.2f} %\033[0K", end="", flush=True)

        con.commit()
        elapsed = perf_counter() - start
        print(f"\nFinished in {elapsed:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())