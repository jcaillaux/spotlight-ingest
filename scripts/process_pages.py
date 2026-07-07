from config import DATA, metadata
from bs4 import BeautifulSoup
from pathlib import Path

import duckdb 

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

def extract_id(href) :
    return href.rstrip('/').split('/')[-1]

def read_html(html_path:Path) -> str :
    with open(html_path, "r") as f :
        return f.read()

def process_html(html):
    soup = BeautifulSoup(markup=html, features='html.parser')

    main = soup.find('main')
    a_tags = main.find_all('a', class_="anons-thumbnail show")
    
    con.executemany(
        "INSERT INTO metadata (id) VALUES (?) ON CONFLICT DO NOTHING",
        [(extract_id(a['href']),) for a in a_tags]
    )

def extract_info(soup):
    title = soup.find_all('h1')
    imgs = soup.find_all('img', class_='aligncenter')
    date = soup.find_all('span', class_="date")

    hash = soup.find_all('pre')

    assert len(title) == 1
    assert len(date)  == 1
    assert len(imgs)  == 2
    assert len(hash)  == 2

def main():
    htmls = (DATA / 'html').glob('*.html')

    for i, html in enumerate(htmls) :
        try :
            hrefs = process_html(read_html(html_path=html))
        except AssertionError :
            print(html) 
    

if __name__ == '__main__':
    main()