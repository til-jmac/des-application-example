-- Typed, renamed, cleaned - still one row per (establishment, source file).
--
-- The extraction script can't filter server-side (the FSA API's
-- maxDistanceLimit parameter is accepted but not actually enforced - see
-- extract/fetch_establishments.py), so the real radius cutoff happens here.
--
-- RatingValue is a VARCHAR in the source data because it isn't always
-- numeric: England/Wales/NI (SchemeType='FHRS') use 0-5, but Scotland
-- (SchemeType='FHIS') uses text like 'Pass'/'Improvement Required', and any
-- establishment awaiting its first inspection uses 'AwaitingInspection' or
-- 'Exempt' regardless of scheme. TRY_CAST returns NULL for the non-numeric
-- cases instead of erroring, which is the semantically correct outcome - an
-- "Awaiting Inspection" business genuinely has no numeric rating yet.
-- Naming convention: source PascalCase columns become snake_case, nested
-- fields get a descriptive suffix instead of staying generic (scores.Hygiene
-- -> hygiene_score, geocode.latitude -> latitude).
CREATE OR REPLACE TABLE stg_establishments AS
SELECT
    FHRSID AS fhrsid,
    LocalAuthorityBusinessID AS local_authority_business_id,
    BusinessName AS business_name,
    BusinessType AS business_type,
    BusinessTypeID AS business_type_id,
    AddressLine1 AS address_line_1,
    AddressLine2 AS address_line_2,
    AddressLine3 AS address_line_3,
    AddressLine4 AS address_line_4,
    PostCode AS postcode,
    RatingValue AS rating_value_raw,
    TRY_CAST(RatingValue AS SMALLINT) AS rating_value_numeric,
    SchemeType AS scheme_type,
    RatingKey AS rating_key,
    CAST(RatingDate AS DATE) AS rating_date,
    NewRatingPending AS new_rating_pending,
    Hygiene AS hygiene_score,
    Structural AS structural_score,
    ConfidenceInManagement AS confidence_in_management_score,
    -- The source API returns these as strings inside the geocode object,
    -- not numbers. TRY_CAST rather than CAST defensively: every
    -- establishment in this particular pull happens to have a geocode, but
    -- the FSA API doesn't guarantee that in general, and a missing geocode
    -- should become NULL here rather than fail the whole model.
    TRY_CAST(longitude AS DOUBLE) AS longitude,
    TRY_CAST(latitude AS DOUBLE) AS latitude,
    LocalAuthorityName AS local_authority_name,
    LocalAuthorityCode AS local_authority_code,
    LocalAuthorityWebSite AS local_authority_website,
    LocalAuthorityEmailAddress AS local_authority_email,
    RightToReply AS right_to_reply,
    Distance AS distance_miles,
    _source_file
FROM raw_establishments
WHERE Distance <= __SEARCH_RADIUS_MILES__;
