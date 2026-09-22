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
    # Fail with a clear instruction rather than a raw "file not found" -
    # this is the single most likely first-run mistake for anyone cloning
    # the repo and jumping straight to `pytest`.
    if not config.DUCKDB_PATH.exists():
        pytest.fail("data/lunch_safety.duckdb not found - run `python sql/run_models.py` first")
    connection = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    yield connection
    connection.close()


def test_mart_has_rows(con):
    # The most basic possible check, but worth having explicitly: an empty
    # table would pass every other test in this file vacuously.
    row_count = con.execute("SELECT count(*) FROM mart_establishments").fetchone()[0]
    assert row_count > 0


def test_no_duplicate_fhrsid(con):
    # Directly tests the dedup logic in sql/03_marts.sql - if the
    # ROW_NUMBER()/QUALIFY-equivalent window function there ever regresses,
    # this is what catches it.
    duplicates = con.execute(
        "SELECT count(*) FROM (SELECT fhrsid FROM mart_establishments GROUP BY fhrsid HAVING count(*) > 1)"
    ).fetchone()[0]
    assert duplicates == 0


def test_no_nulls_in_required_columns(con):
    # Deliberately not testing every column - rating_value_numeric, for
    # example, is SUPPOSED to be null for non-numeric ratings (see
    # sql/02_staging.sql). Only checking the columns that should never be
    # missing regardless of scheme or rating status.
    for column in ("fhrsid", "business_name", "distance_miles"):
        null_count = con.execute(
            f"SELECT count(*) FROM mart_establishments WHERE {column} IS NULL"
        ).fetchone()[0]
        assert null_count == 0, f"unexpected NULLs in {column}"


def test_every_row_within_search_radius(con):
    # Guards the client-side radius cutoff in sql/02_staging.sql - the API
    # itself doesn't enforce this (see extract/fetch_establishments.py), so
    # this is the only thing standing between "lunch near the office" and
    # "lunch somewhere in the UK".
    over_radius = con.execute(
        "SELECT count(*) FROM mart_establishments WHERE distance_miles > ?",
        [config.SEARCH_RADIUS_MILES],
    ).fetchone()[0]
    assert over_radius == 0


def test_rating_value_numeric_matches_rating_category(con):
    # Cross-checks the two derived rating columns agree with each other for
    # every FHRS-scheme (numeric) establishment, catching a mistake in
    # either the TRY_CAST or the rating_category CASE statement without
    # having to duplicate that logic here.
    mismatched = con.execute(
        """
        SELECT count(*) FROM mart_establishments
        WHERE rating_value_numeric IS NOT NULL
          AND rating_category != CAST(rating_value_numeric AS VARCHAR)
        """
    ).fetchone()[0]
    assert mismatched == 0
