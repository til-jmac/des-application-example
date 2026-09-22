-- One row per establishment (fhrsid), deduplicated across every raw snapshot
-- pulled so far, with the flags the app is built around.
--
-- Idempotency: this is a full CREATE OR REPLACE rebuild from every committed
-- raw file every time it runs, not an incremental merge. At this data
-- volume (a few hundred rows) a full rebuild costs milliseconds and is
-- trivially correct - re-running against unchanged raw files reproduces an
-- identical table, and a new raw snapshot deterministically keeps the most
-- recent record per establishment. See README for why this beats
-- incremental merge at this scale.
CREATE OR REPLACE TABLE mart_establishments AS
WITH deduped AS (
    SELECT
        *,
        -- rating_date DESC picks the record with the newer rating first -
        -- if a rating genuinely changed between two raw pulls, its
        -- RatingDate moves forward too, so this is a real "most current"
        -- ordering rather than just "most recently downloaded". _source_file
        -- DESC is only a tiebreak for when nothing changed between runs (the
        -- common case) - it sorts chronologically because filenames are
        -- timestamp-prefixed.
        ROW_NUMBER() OVER (
            PARTITION BY fhrsid
            ORDER BY rating_date DESC NULLS LAST, _source_file DESC
        ) AS _row_number
    FROM stg_establishments
)
SELECT
    fhrsid,
    business_name,
    business_type,
    business_type_id,
    -- Deliberately scoped to places you'd actually get lunch from - the raw
    -- pull also includes supermarkets, importers/exporters and a school,
    -- which aren't relevant to the "where should I eat" persona. IDs are the
    -- FSA's own BusinessTypeID: 1 = Restaurant/Cafe/Canteen, 7841 = Other
    -- catering premises, 7843 = Pub/bar/nightclub, 7844 = Takeaway/sandwich
    -- shop, 7846 = Mobile caterer.
    business_type_id IN (1, 7841, 7843, 7844, 7846) AS is_lunch_relevant,
    address_line_1,
    address_line_2,
    address_line_3,
    address_line_4,
    postcode,
    rating_value_raw,
    rating_value_numeric,
    -- A human-readable version of whichever of rating_value_raw /
    -- rating_value_numeric is actually populated for this row, so the app
    -- doesn't need to know about the FHRS/FHIS split at all - it just reads
    -- one column.
    CASE
        WHEN rating_value_numeric IS NOT NULL THEN CAST(rating_value_numeric AS VARCHAR)
        ELSE lower(replace(rating_value_raw, ' ', '_'))
    END AS rating_category,
    scheme_type,
    rating_date,
    new_rating_pending,
    hygiene_score,
    structural_score,
    confidence_in_management_score,
    distance_miles,
    longitude,
    latitude,
    local_authority_name,
    -- 18 months is a flat, simple proxy, not the FSA's actual policy - real
    -- inspection frequency is risk-banded (roughly 6-24+ months depending on
    -- the premises). Good enough to flag "this hasn't been looked at in a
    -- while" without claiming to model FSA policy exactly.
    rating_date IS NOT NULL AND rating_date < CURRENT_DATE - INTERVAL 18 MONTH AS is_overdue_for_reinspection,
    -- Passed straight through from the API rather than derived - it's
    -- already the single most direct "a rating is about to change" signal
    -- available, so there's nothing to compute.
    new_rating_pending AS is_new_rating_pending,
    -- A proxy for "this rating is fresh", not "this rating just changed" -
    -- telling those apart for real needs a prior raw snapshot to compare
    -- against (see README "How it works").
    rating_date IS NOT NULL AND rating_date >= CURRENT_DATE - INTERVAL 3 MONTH AS is_recently_rated
FROM deduped
WHERE _row_number = 1;
