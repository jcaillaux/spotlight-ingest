import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path

    ROOT = Path(__file__).parent.parent

    sys.path.insert(0, str(ROOT))
    return


@app.cell
def _():
    from config import metadata
    import duckdb

    return duckdb, metadata


@app.cell
def _(duckdb, metadata):
    con = duckdb.connect(metadata)
    return (con,)


@app.cell
def _(con):
    con.execute(
        """
            SELECT * FROM images LIMIT 2;
        """
    ).df()
    return


@app.cell
def _(con):
    con.execute(
        """
            SELECT * FROM images WHERE sha256 is null limit 10;
        """
    ).df()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
