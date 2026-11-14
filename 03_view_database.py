"""Step 3: Read and verify stored data, including tariff-based pass prices."""
import sqlite3
from pathlib import Path

import pandas as pd

DATABASE = Path(__file__).resolve().parent / "transport.db"


def load_table():
    """Read commuting data and associate prices with verified zone counts."""
    with sqlite3.connect(DATABASE) as db:
        return pd.read_sql_query("""
            SELECT
                c.municipality,
                c.station,
                c.station_zone,
                c.route_zone_count,
                c.median_minutes AS one_way_minutes,
                c.sampled_connections,
                p.label AS pass_type,
                p.monthly_chf AS monthly_pass_chf,
                p.annual_chf AS annual_pass_chf,
                ROUND(p.annual_chf / 12.0, 2) AS annual_pass_per_month_chf
            FROM commutes AS c
            LEFT JOIN zvv_pass_prices AS p ON p.tariff_level =
                CASE
                    WHEN c.route_zone_count IS NULL THEN NULL
                    WHEN c.route_zone_count >= 6 THEN 6
                    WHEN c.route_zone_count <= 2 THEN 2
                    ELSE c.route_zone_count
                END
            ORDER BY c.median_minutes ASC
        """, db)


def main():
    if not DATABASE.exists():
        print("Database missing. Run: python 02_build_database.py")
        return
    table = load_table()
    print(table.to_string(index=False, na_rep="not yet verified"))
    print("\nNOTE: station_zone != route_zone_count. Verify each journey in the ZVV zone map.")
    print("NOTE: these are pre-13-Dec-2026 tariffs. Update after fare changes.")


if __name__ == "__main__":
    main()
