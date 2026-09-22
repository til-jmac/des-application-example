"""
Lunch Safety Finder - read-only view over mart_establishments.

All the logic (flags, categories, dedup) lives in the SQL models; this app
only queries and displays.
"""

import sys
from pathlib import Path

import duckdb
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

st.set_page_config(page_title="Lunch Safety Finder", layout="wide")


@st.cache_resource
def get_connection():
    # read_only=True means this app can never accidentally write to the
    # database - it only ever displays what sql/run_models.py already built.
    # @st.cache_resource keeps one connection alive across Streamlit reruns
    # instead of reopening the file on every filter change.
    return duckdb.connect(str(config.DUCKDB_PATH), read_only=True)


con = get_connection()
# Pulled into a plain pandas DataFrame once - the dataset is a few hundred
# rows, so filtering in memory below is simpler than re-querying DuckDB per
# filter change, and keeps all the actual modelling logic in the SQL layer.
df = con.execute("SELECT * FROM mart_establishments").df()

st.title("Lunch Safety Finder")
st.caption(
    f"Food hygiene ratings within {config.SEARCH_RADIUS_MILES} miles of "
    f"{config.OFFICE_ADDRESS} — a walkable lunch radius from The Information "
    f"Lab's City of London office."
)

with st.sidebar:
    st.header("Filters")
    # Defaults to True: the raw pull includes supermarkets, importers and a
    # school (see sql/03_marts.sql), which aren't lunch options. Defaulting
    # this off would make the app's first impression a pile of irrelevant
    # results.
    lunch_only = st.checkbox("Lunch-relevant places only (hide retailers, etc.)", value=True)
    max_distance = st.slider(
        "Max distance (miles)", 0.0, float(config.SEARCH_RADIUS_MILES), float(config.SEARCH_RADIUS_MILES), 0.01
    )
    # Options for both multiselects are read from the data itself rather
    # than hardcoded, so they can't drift out of sync with what's actually
    # in mart_establishments.
    categories = sorted(df["rating_category"].dropna().unique().tolist())
    selected_categories = st.multiselect("Rating", categories, default=categories)
    business_types = sorted(df["business_type"].dropna().unique().tolist())
    selected_types = st.multiselect("Business type", business_types, default=business_types)
    overdue_only = st.checkbox("Overdue for reinspection only", value=False)
    fresh_only = st.checkbox("Recently rated / new rating pending only", value=False)

# Base filters apply unconditionally; the three checkbox filters below are
# layered on top only when ticked, so unchecking everything shows all 332
# establishments rather than an empty table.
filtered = df[
    (df["distance_miles"] <= max_distance)
    & (df["rating_category"].isin(selected_categories))
    & (df["business_type"].isin(selected_types))
]
if lunch_only:
    filtered = filtered[filtered["is_lunch_relevant"]]
if overdue_only:
    filtered = filtered[filtered["is_overdue_for_reinspection"]]
if fresh_only:
    # OR, not AND: "fresh" means either the rating changed recently or a new
    # one is about to land - either is a reason to double check before you go.
    filtered = filtered[filtered["is_recently_rated"] | filtered["is_new_rating_pending"]]

col1, col2, col3 = st.columns(3)
col1.metric("Places shown", len(filtered))
col2.metric("Overdue for reinspection", int(filtered["is_overdue_for_reinspection"].sum()))
col3.metric("Rated 5", int((filtered["rating_category"] == "5").sum()))

# st.map needs columns named exactly "lat"/"lon"; dropna() because a handful
# of establishments have no geocode in the source data and would otherwise
# error the map out entirely rather than just being skipped.
st.map(
    filtered.rename(columns={"latitude": "lat", "longitude": "lon"})[["lat", "lon"]].dropna(),
    size=15,
)

display_columns = [
    "business_name",
    "business_type",
    "rating_category",
    "distance_miles",
    "rating_date",
    "is_overdue_for_reinspection",
    "is_recently_rated",
    "is_new_rating_pending",
    "address_line_1",
    "postcode",
]
# Overdue places sort to the top first, then nearest-first within each group
# - surfacing the thing you'd actually want to notice before the thing
# that's merely closest.
st.dataframe(
    filtered[display_columns].sort_values(["is_overdue_for_reinspection", "distance_miles"], ascending=[False, True]),
    use_container_width=True,
    hide_index=True,
)
