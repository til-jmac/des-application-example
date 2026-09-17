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
    return duckdb.connect(str(config.DUCKDB_PATH), read_only=True)


con = get_connection()
df = con.execute("SELECT * FROM mart_establishments").df()

st.title("Lunch Safety Finder")
st.caption(
    f"Food hygiene ratings within {config.SEARCH_RADIUS_MILES} miles of "
    f"{config.OFFICE_ADDRESS} — a walkable lunch radius from The Information "
    f"Lab's City of London office."
)

with st.sidebar:
    st.header("Filters")
    lunch_only = st.checkbox("Lunch-relevant places only (hide retailers, etc.)", value=True)
    max_distance = st.slider(
        "Max distance (miles)", 0.0, float(config.SEARCH_RADIUS_MILES), float(config.SEARCH_RADIUS_MILES), 0.01
    )
    categories = sorted(df["rating_category"].dropna().unique().tolist())
    selected_categories = st.multiselect("Rating", categories, default=categories)
    business_types = sorted(df["business_type"].dropna().unique().tolist())
    selected_types = st.multiselect("Business type", business_types, default=business_types)
    overdue_only = st.checkbox("Overdue for reinspection only", value=False)
    fresh_only = st.checkbox("Recently rated / new rating pending only", value=False)

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
    filtered = filtered[filtered["is_recently_rated"] | filtered["is_new_rating_pending"]]

col1, col2, col3 = st.columns(3)
col1.metric("Places shown", len(filtered))
col2.metric("Overdue for reinspection", int(filtered["is_overdue_for_reinspection"].sum()))
col3.metric("Rated 5", int((filtered["rating_category"] == "5").sum()))

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
st.dataframe(
    filtered[display_columns].sort_values(["is_overdue_for_reinspection", "distance_miles"], ascending=[False, True]),
    use_container_width=True,
    hide_index=True,
)
