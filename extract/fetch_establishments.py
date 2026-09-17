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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def fetch_page(page_number: int) -> dict:
    response = requests.get(
        config.FHRS_API_BASE_URL,
        headers={
            "x-api-version": config.FHRS_API_VERSION,
            "User-Agent": "des-application-example (data-engineering-school example project)",
        },
        params={
            "latitude": config.OFFICE_LATITUDE,
            "longitude": config.OFFICE_LONGITUDE,
            "maxDistanceLimit": config.SEARCH_RADIUS_MILES,
            "sortOptionKey": "distance",
            "pageNumber": page_number,
            "pageSize": config.PAGE_SIZE,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def page_has_establishment_within_radius(payload: dict) -> bool:
    establishments = payload.get("establishments", [])
    if not establishments:
        return False
    closest_distance = min(e["Distance"] for e in establishments)
    return closest_distance <= config.SEARCH_RADIUS_MILES


def main():
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    page_number = 1
    pages_written = 0
    while True:
        payload = fetch_page(page_number)
        if not page_has_establishment_within_radius(payload):
            break

        out_path = (
            config.RAW_DATA_DIR
            / f"establishments_run-{run_timestamp}_page-{page_number}.json"
        )
        out_path.write_text(json.dumps(payload, indent=2))
        pages_written += 1
        print(f"wrote {out_path.name} ({len(payload.get('establishments', []))} establishments)")

        total_pages = payload.get("meta", {}).get("totalPages")
        if total_pages is not None and page_number >= total_pages:
            break
        page_number += 1

    if pages_written == 0:
        raise RuntimeError("No establishments found within the search radius - nothing written")

    print(f"done: {pages_written} page(s) written for run {run_timestamp}")


if __name__ == "__main__":
    main()
