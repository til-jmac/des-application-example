-- Load every committed raw API response page and explode the establishments
-- array into one row per establishment, tagged with which file it came from.
-- `unnest(..., recursive := true)` also flattens the nested `geocode` and
-- `scores` structs straight into top-level columns (e.g. `latitude`,
-- `Hygiene`), which staging then renames/types properly.
CREATE OR REPLACE TABLE raw_establishments AS
SELECT
    filename AS _source_file,
    unnest(establishments, recursive := true)
FROM read_json_auto('__RAW_GLOB__', filename = true);
