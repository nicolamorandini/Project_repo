"""Optional: A tiny Streamlit preview, not the complete group application."""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_FILE = Path(__file__).resolve().parent / "transport.db"

st.set_page_config(page_title="Where Should I Live? - Transport", layout="wide")
st.title("Where Should I Live? - Commuting data")
st.caption("Demo of the transport module. Not the final relocation ranking.")

if not DB_FILE.exists():
    st.warning("Please first run: python 02_build_database.py")
    st.stop()

with sqlite3.connect(DB_FILE) as db:
    data = pd.read_sql_query("""
        SELECT c.municipality, c.station, c.station_zone,
               c.route_zone_count, c.median_minutes,
               p.monthly_chf, p.annual_chf
        FROM commutes AS c
        LEFT JOIN zvv_pass_prices AS p
            ON p.tariff_level = CASE
                WHEN c.route_zone_count IS NULL THEN NULL
                WHEN c.route_zone_count >= 6 THEN 6
                WHEN c.route_zone_count <= 2 THEN 2
                ELSE c.route_zone_count
            END
        ORDER BY c.median_minutes ASC
    """, db)

st.dataframe(data, hide_index=True, use_container_width=True)
valid = data.dropna(subset=["median_minutes"])
if not valid.empty:
    st.subheader("Travel time by municipality (minutes, one way)")
    st.bar_chart(valid.set_index("municipality")["median_minutes"])
st.info("Pass prices appear only once the route zone counts have been manually verified and entered into municipalities.csv.")
