import duckdb
from config import metadata
from loguru import logger

def main():
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
    con.close()
    logger.success(f"Database initialized at {metadata}")

if __name__ == '__main__':
    main()
