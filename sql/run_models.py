"""
Build data/lunch_safety.duckdb from the committed raw JSON by running the
numbered SQL files in this folder in order. No network access needed - it
only ever reads data/raw/*.json.
"""

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def run():
    config.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH))

    sql_files = sorted(config.SQL_DIR.glob("[0-9]*.sql"))
    if not sql_files:
        raise RuntimeError(f"No numbered SQL model files found in {config.SQL_DIR}")

    raw_glob = str(config.RAW_DATA_DIR / "*.json")

    for sql_file in sql_files:
        sql = sql_file.read_text()
        sql = sql.replace("__RAW_GLOB__", raw_glob)
        sql = sql.replace("__SEARCH_RADIUS_MILES__", str(config.SEARCH_RADIUS_MILES))
        print(f"running {sql_file.name}")
        con.execute(sql)

    row_count = con.execute("SELECT count(*) FROM mart_establishments").fetchone()[0]
    print(f"done: mart_establishments has {row_count} rows")
    con.close()


if __name__ == "__main__":
    run()
