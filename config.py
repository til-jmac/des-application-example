from pathlib import Path

# The Information Lab's City of London office (25 Watling Street, EC4M 9BR),
# geocoded via postcodes.io.
OFFICE_ADDRESS = "25 Watling Street, London EC4M 9BR"
OFFICE_LATITUDE = 51.513016
OFFICE_LONGITUDE = -0.093946

# A ~5 minute walk. Chosen to keep the dataset a walkable lunch radius rather
# than an arbitrary distance - see README for how this was picked.
SEARCH_RADIUS_MILES = 0.25

FHRS_API_BASE_URL = "https://api.ratings.food.gov.uk/Establishments"
FHRS_API_VERSION = "2"
PAGE_SIZE = 100

REPO_ROOT = Path(__file__).resolve().parent
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
DUCKDB_PATH = REPO_ROOT / "data" / "lunch_safety.duckdb"
SQL_DIR = REPO_ROOT / "sql"
