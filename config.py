from pathlib import Path

# The Information Lab's City of London office (25 Watling Street, EC4M 9BR),
# geocoded once via postcodes.io rather than hand-estimated - the FHRS API
# takes decimal lat/long, not a postcode.
OFFICE_ADDRESS = "25 Watling Street, London EC4M 9BR"
OFFICE_LATITUDE = 51.513016
OFFICE_LONGITUDE = -0.093946

# A ~5 minute walk. Chosen deliberately, not left at an API default: this
# part of the City is dense enough that even 0.25 miles returns ~330
# establishments across 4 pages, so anything larger would stop being a
# "walkable lunch options" dataset and start being "most of the City of
# London". See README for how this was picked.
SEARCH_RADIUS_MILES = 0.25

FHRS_API_BASE_URL = "https://api.ratings.food.gov.uk/Establishments"
# The FSA API requires this header on every request but no API key - see
# https://api.ratings.food.gov.uk/help
FHRS_API_VERSION = "2"
PAGE_SIZE = 100

# Everything else is derived from the repo's own location, not hardcoded, so
# the pipeline still works if the repo is cloned somewhere else.
REPO_ROOT = Path(__file__).resolve().parent
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
DUCKDB_PATH = REPO_ROOT / "data" / "lunch_safety.duckdb"
SQL_DIR = REPO_ROOT / "sql"
