"""
Pull FHRS establishments near the office from the FSA ratings API and commit
the raw response pages exactly as returned, before any cleaning happens.

The API's `maxDistanceLimit` parameter does NOT actually filter results
server-side - it's accepted but ignored (confirmed by testing: `totalCount`
in the response `meta` stays at the full nationwide count regardless of the
value passed). Only `sortOptionKey=distance` affects anything, by sorting the
whole dataset by proximity. So this script does the real radius cutoff
itself: it keeps paging while a page still contains at least one
establishment inside SEARCH_RADIUS_MILES, and stops once a page's closest
establishment falls outside it. Every page it does fetch is written
to disk unmodified - including the final "boundary" page, which may contain
a handful of establishments just outside the radius. Filtering those out is
the SQL layer's job, not extraction's.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# config.py lives at the repo root, one level up from this script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def fetch_page(page_number: int) -> dict:
    """Fetch one page of establishments sorted by distance from the office."""
    response = requests.get(
        config.FHRS_API_BASE_URL,
        headers={
            "x-api-version": config.FHRS_API_VERSION,
            # Polite to identify the caller even though the API needs no auth.
            "User-Agent": "des-application-example (data-engineering-school example project)",
        },
        params={
            "latitude": config.OFFICE_LATITUDE,
            "longitude": config.OFFICE_LONGITUDE,
            # Sent for documentation/intent even though it isn't enforced
            # server-side (see module docstring) - the real cutoff happens
            # in page_has_establishment_within_radius() below and again in
            # sql/02_staging.sql.
            "maxDistanceLimit": config.SEARCH_RADIUS_MILES,
            # This is the parameter that actually matters: without it the
            # API returns results in an arbitrary (roughly alphabetical)
            # order, not sorted by proximity at all.
            "sortOptionKey": "distance",
            "pageNumber": page_number,
            "pageSize": config.PAGE_SIZE,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def page_has_establishment_within_radius(payload: dict) -> bool:
    """
    True if any establishment on this page is within SEARCH_RADIUS_MILES.

    Because results are sorted by distance, the closest establishment on the
    page tells us whether it's worth fetching further pages at all - once
    even the closest one is outside the radius, every later page will be too.
    """
    establishments = payload.get("establishments", [])
    if not establishments:
        return False
    closest_distance = min(e["Distance"] for e in establishments)
    return closest_distance <= config.SEARCH_RADIUS_MILES


def main():
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    # One timestamp for the whole run, shared by every page written this
    # call, so a run's pages can be told apart from a different run's later.
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    page_number = 1
    pages_written = 0
    while True:
        payload = fetch_page(page_number)
        if not page_has_establishment_within_radius(payload):
            # Nothing on this page (or any later page) is close enough to
            # matter - stop paging. This page itself is NOT written, since
            # committing it would just be nationwide noise with nothing
            # inside the radius.
            break

        out_path = (
            config.RAW_DATA_DIR
            / f"establishments_run-{run_timestamp}_page-{page_number}.json"
        )
        # Write the page exactly as returned - no filtering, no reshaping.
        # This IS the raw commit the rubric asks for; cleaning happens later,
        # in SQL, against these files.
        out_path.write_text(json.dumps(payload, indent=2))
        pages_written += 1
        print(f"wrote {out_path.name} ({len(payload.get('establishments', []))} establishments)")

        # meta.totalPages reflects the nationwide result set (see module
        # docstring), so this is really just a safety net against an
        # infinite loop if the API ever stops returning establishments
        # without also stopping being "within radius" - it shouldn't fire
        # in practice for a small geographic slice like this one.
        total_pages = payload.get("meta", {}).get("totalPages")
        if total_pages is not None and page_number >= total_pages:
            break
        page_number += 1

    if pages_written == 0:
        # Fail loudly rather than silently leaving a run with zero raw
        # files - that would look like "nothing changed" to run_models.py
        # instead of "something's wrong with the search".
        raise RuntimeError("No establishments found within the search radius - nothing written")

    print(f"done: {pages_written} page(s) written for run {run_timestamp}")


if __name__ == "__main__":
    main()
