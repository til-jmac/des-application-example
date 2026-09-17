"""
Smoke tests for the mart model. Run `python sql/run_models.py` first so
data/lunch_safety.duckdb exists.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


@pytest.fixture(scope="module")
def con():
    if not config.DUCKDB_PATH.exists():
        pytest.fail("data/lunch_safety.duckdb not found - run `python sql/run_models.py` first")
    connection = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    yield connection
    connection.close()


def test_mart_has_rows(con):
    row_count = con.execute("SELECT count(*) FROM mart_establishments").fetchone()[0]
    assert row_count > 0


def test_no_duplicate_fhrsid(con):
    duplicates = con.execute(
        "SELECT count(*) FROM (SELECT fhrsid FROM mart_establishments GROUP BY fhrsid HAVING count(*) > 1)"
    ).fetchone()[0]
    assert duplicates == 0


def test_no_nulls_in_required_columns(con):
    for column in ("fhrsid", "business_name", "distance_miles"):
        null_count = con.execute(
            f"SELECT count(*) FROM mart_establishments WHERE {column} IS NULL"
        ).fetchone()[0]
        assert null_count == 0, f"unexpected NULLs in {column}"


def test_every_row_within_search_radius(con):
    over_radius = con.execute(
        "SELECT count(*) FROM mart_establishments WHERE distance_miles > ?",
        [config.SEARCH_RADIUS_MILES],
    ).fetchone()[0]
    assert over_radius == 0


def test_rating_value_numeric_matches_rating_category(con):
    mismatched = con.execute(
        """
        SELECT count(*) FROM mart_establishments
        WHERE rating_value_numeric IS NOT NULL
          AND rating_category != CAST(rating_value_numeric AS VARCHAR)
        """
    ).fetchone()[0]
    assert mismatched == 0
