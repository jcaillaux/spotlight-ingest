import asyncio
import aiohttp
from time import perf_counter
from bs4 import BeautifulSoup
from typing import Optional
from config import SPOTLIGHT_REPO, DATA, LOGS, HEADERS
from pathlib import Path
from loguru import logger

logger.add(LOGS / 'page_gathering.log', rotation='5 MB')


def make_url(host: str, page:Optional[int]=None) -> str :
    """Build a URL from a host and an optional page number.

    Args:
        host: The base hostname.
        page: Optional page number to append.

    Returns:
        The constructed URL string.
    """
    return f"https://{host}{'/' + str(page) if page is not None else ''}"

def make_dest(page:int) -> Path :
    """Build the destination file path for a given page number.

    Args:
        page: The page number.

    Returns:
        Path to the HTML file for this page.
    """
    return DATA / 'html' / f"{page}.html"

def last_page_number() -> int :
    """Return the highest page number among downloaded HTML files.

    Returns:
        The largest page number found, or 0 if none exist.
    """
    html_path = DATA / 'html'

    html_index = max((
            int(file.stem) 
            for file in html_path.glob('*.html')
        ), default=0
    )

    return html_index
        

def extract_page_number(html:str) -> int:
    """Extract the last page number from the pagination nav in an HTML string.

    Args:
        html: Raw HTML content containing pagination navigation.

    Returns:
        The highest page number found in the pagination links.
    """
    soup = BeautifulSoup(markup=html,features='html.parser')
    navs = soup.find_all("nav")

    # 2 navs should be present

    assert len(navs) == 2

    # The one of interest is the last one

    links = navs[1].find_all("a")
    
    return max(
        int(part)
        for a in links
        if (part := a.get('href').rstrip('/').split('/')[-1]).isdigit()
    )

def write_html(html:str, dest:Path):
    """Write an HTML string to a file.

    Args:
        html: The HTML content to write.
        dest: The destination file path.
    """
    logger.info(f"Writing to {dest}...")
    with open(dest, "w") as f:
        f.write(html)
    logger.success(f"writing to {dest}, DONE.")
    
async def fetch_page(session : aiohttp.ClientSession, i:int=1) -> str:
    """Fetch a single listing page from the repository.

    Args:
        session: The aiohttp client session.
        i: The page number to fetch (1-based).

    Returns:
        The raw HTML content of the page.

    Raises:
        aiohttp.ClientResponseError: If the HTTP request fails.
    """

    target_url = f"{make_url(host=SPOTLIGHT_REPO)}{'/page/' + str(i) if i > 1 else ''}" 

    logger.info(f"Fetching {target_url}...")
    async with session.get(url=target_url) as response :

        response.raise_for_status()

        html = await response.text()

        logger.success(f"Fetching {target_url} DONE.")
        
        return html

async def main():
    start = perf_counter()
    i = last_page_number() + 1
    
    n_page = None

    async with aiohttp.ClientSession(headers=HEADERS) as session :
        while True :
            try :
                logger.info(f"Processing page {i}...")
                html = await fetch_page(session=session, i=i)
                write_html(html=html, dest=make_dest(page=i))
                if n_page is None :
                    n_page = extract_page_number(html = html)
                logger.success(f"Processing page {i} DONE.")

                assert n_page is not None

            except AssertionError : 
                break
            except Exception as e:
                logger.warning(f"Page {i} encountered an issue\n{e}")
                if n_page is None :
                    logger.info("No more work.") 
                    break
            i +=1
            if i > n_page :
                break

    elapsed = perf_counter() - start
    logger.success(f"Finished in {elapsed:.2f}s")


if __name__ == "__main__":
    try :
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopping ...")