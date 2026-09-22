# Lunch Safety Finder

> **Note:** This is a worked example The Information Lab built to show
> Data Engineering School candidates what a strong submission looks like -
> not a real applicant's project. See "Where AI helped" below for how it
> was built.

## What I built and who for
A tool for office workers near The Information Lab's City of London office (25 Watling Street, EC4M 9BR) who are deciding where to eat lunch. It pulls UK Food Hygiene Rating Scheme data for everywhere within a 0.25-mile walk of the office, models it into one clean table, and surfaces it in a small Streamlit app with two things a plain ratings list skips: places **overdue for reinspection**, and places with a rating that's **recently changed or about to**.

![Lunch Safety Finder app screenshot](docs/app-screenshot.png)

## The data
[FSA Food Hygiene Rating Scheme (FHRS) API](https://api.ratings.food.gov.uk/help). Free, no API key or registration - just a required `x-api-version: 2` header. The FSA publishes it under the Open Government Licence.

The extraction script queries the `Establishments` endpoint, searching by distance from the office's coordinates (geocoded once via [postcodes.io](https://postcodes.io)) and sorting by proximity.

**A quirk worth flagging:** the API accepts `maxDistanceLimit` but doesn't filter with it. `meta.totalCount` stays at the full nationwide count (about 15,800) no matter what value you pass. Only `sortOptionKey=distance` does anything, and it sorts the entire dataset. So the extraction script pages through the distance-sorted results itself and stops once a page's closest establishment falls outside the radius. The real filtering happens in SQL, not at the API.

## How it works
Three SQL layers build `data/lunch_safety.duckdb` (via `sql/run_models.py`), and a Streamlit app reads the result:

1. **`raw_establishments`** (`sql/01_raw.sql`): loads every committed file in `data/raw/` and unnests the `establishments` array into one row per establishment, tagged with its source file.
2. **`stg_establishments`** (`sql/02_staging.sql`): typed, renamed, cleaned. This is also where the real radius cutoff happens (`WHERE Distance <= 0.25`), since the API doesn't enforce it. `RatingValue` comes back as text because it isn't always numeric: England/Wales/NI (`FHRS` scheme) use 0-5, but Scotland (`FHIS` scheme) uses `Pass`/`Improvement Required`, and anything awaiting its first inspection uses `AwaitingInspection`/`Exempt` regardless of scheme. `TRY_CAST` turns the non-numeric cases into `NULL` instead of erroring, which is correct: those establishments have no numeric rating yet. Nothing in this pull is Scottish, but the model still handles `FHIS` correctly rather than assuming England-only data forever.
3. **`mart_establishments`** (`sql/03_marts.sql`): one row per `fhrsid`, deduplicated across every raw snapshot pulled so far (`ROW_NUMBER() OVER (PARTITION BY fhrsid ORDER BY rating_date DESC, _source_file DESC)`), plus the derived columns the app uses:
   - **`is_lunch_relevant`**: the raw pull also includes supermarkets, importers/exporters and a school. This flags the business types you'd get lunch from.
   - **`is_overdue_for_reinspection`**: no rating in the last 18 months. A simple, flat proxy chosen on purpose - the FSA's real inspection frequency is risk-based (6-24+ months depending on premises risk), not a fixed interval.
   - **`is_new_rating_pending`**: a direct passthrough of the API's own `NewRatingPending` field - the clearest "about to change" signal available.
   - **`is_recently_rated`**: rated in the last 3 months.
4. **Streamlit app** (`app/lunch_safety_app.py`): reads `mart_establishments` directly, read-only, no logic recomputed. Sidebar filters by distance, rating and business type, a map, and a results table sorted to put overdue places first.

**Idempotency:** every model does a full `CREATE OR REPLACE TABLE` rebuild from all committed raw files, every run. No incremental merge. At a few hundred rows this costs milliseconds and is easy to get right: re-running against unchanged raw data reproduces an identical table (verified - the two raw snapshots in `data/raw/`, pulled about 20 minutes apart, both rebuild to the same 332-row mart), and a new snapshot keeps the most recent record per establishment.

**What genuine "rating changed" detection would need:** raw files are immutable and timestamped so this is possible later. A self-join of the two most recent snapshots per `fhrsid` would catch a real change. It isn't built yet - with only two snapshots so far it wouldn't add much, so the three proxy flags above stand in for it until there's more raw history (see "What I would do next").

## How to run it
```
git clone <repo> && cd <repo>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python sql/run_models.py            # builds data/lunch_safety.duckdb from the committed raw JSON - no network needed
streamlit run app/lunch_safety_app.py

# optional, needs network - refreshes data/raw/ from the live API:
python extract/fetch_establishments.py
```
No credentials of any kind are needed. The FHRS API requires none.

Run the tests with `python -m pytest tests/` (checks: mart has rows, no duplicate `fhrsid`, no unexpected nulls, everything within the search radius, rating category matches the numeric rating).

## What I would do next
- Parameterise the office location instead of hardcoding one address, so the same pipeline works for any office.
- True run-over-run change detection (self-join across raw snapshots) instead of the three proxy flags, once there's enough raw history to make it worthwhile.
- Switch the reinspection threshold from a flat 18 months to something risk-band-aware, using `BusinessTypeID` as a rough proxy for inspection frequency.
- Move from full-rebuild to incremental if the raw history grows large enough that milliseconds stop being milliseconds.

## Where AI helped
Claude Code built this project end-to-end, directed by The Information Lab's Data Engineering School team. AI handled the research (confirming the FHRS API needs no auth, discovering the `maxDistanceLimit`/`sortOptionKey` behaviour above by testing real requests since the docs don't mention it), the technical design (the raw/staging/mart split, the idempotency strategy, the flag logic), and the implementation. The human side of this was choosing the API/topic and the lunch-near-the-office persona, reviewing and approving the plan before any code was written, and verifying the results rather than hand-writing the code - the test suite passing, and the mart staying at 332 rows across two real raw pulls taken about 20 minutes apart.

We're showing this process on purpose: you're welcome to use AI to enhance your own submission, the same as we did here. What we look for is whether you can explain your work and the decisions behind it, not whether you typed every line yourself.
