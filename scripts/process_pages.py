from config import DATA, LOGS, metadata
from bs4 import BeautifulSoup
from pathlib import Path
from loguru import logger
from concurrent.futures import ProcessPoolExecutor

import duckdb

logger.add(LOGS / 'process_pages.log', rotation='5 MB')


def extract_id(href):
    return href.rstrip('/').split('/')[-1]


def read_html(html_path: Path) -> str:
    with open(html_path, "r") as f:
        return f.read()


def parse_html(html_path: Path) -> list[str]:
    html = read_html(html_path)
    soup = BeautifulSoup(markup=html, features='html.parser')
    main = soup.find('main')
    a_tags = main.find_all('a', class_="anons-thumbnail show")
    return [extract_id(a['href']) for a in a_tags]


def init_db():
    con = duckdb.connect(metadata)
    con.sql("""
    CREATE TABLE IF NOT EXISTS metadata (
        id VARCHAR PRIMARY KEY,
        date TIMESTAMP,
        title VARCHAR
    );

    CREATE TABLE IF NOT EXISTS images (
        id_meta VARCHAR REFERENCES metadata(id),
        url VARCHAR,
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
    """)
    return con


def main():
    htmls = sorted((DATA / 'html').glob('*.html'))
    logger.info(f"Found {len(htmls)} HTML files to process")

    all_ids = []
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(parse_html, html): html for html in htmls}
        for future in futures:
            html_path = futures[future]
            try:
                ids = future.result()
                logger.info(f"Found {len(ids)} entries in {html_path.name}")
                all_ids.extend(ids)
            except Exception as e:
                logger.warning(f"{html_path.name} encountered an issue: {e}")

    logger.info(f"Inserting {len(all_ids)} entries into database...")
    con = init_db()
    con.executemany(
        "INSERT INTO metadata (id) VALUES (?) ON CONFLICT DO NOTHING",
        [(id,) for id in all_ids]
    )

    total = con.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
    logger.success(f"Done. {total} entries in metadata table.")


if __name__ == '__main__':
    main()
