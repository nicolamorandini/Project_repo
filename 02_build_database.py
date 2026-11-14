"""Steps 2 and 3: Fetch transport times and store results in SQLite.

Edit route_zone_count in municipalities.csv after verifying the routes using the
ZVV tariff-zone map. The station_zone column ALONE is insufficient for pricing.
Run this script once to collect a timetable snapshot; avoid repeated API calls.
"""
import argparse
import csv
import re
import sqlite3
import statistics
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

FOLDER = Path(__file__).resolve().parent
DATABASE = FOLDER / "transport.db"
CSV_PATH = FOLDER / "municipalities.csv"
API_URL = "https://transport.opendata.ch/v1/connections"
DESTINATION = "Zürich HB"
COMMUTE_TIME = "08:00"  # Departures from 08:00 on the chosen weekday
SAMPLE_LIMIT = 4

# Adult, personal ZVV NetzPass, 2nd class; prices valid from 14 Dec 2025.
# Official source: https://www.zvv.ch/de/abos-und-tickets/abos/monats-und-jahresabo.html
# Check for new prices from 13 Dec 2026 before using as current prices.
FARES = [
    (2, "1-2 zones", 88.0, 813.0),
    (3, "3 zones", 130.0, 1200.0),
    (4, "4 zones", 171.0, 1579.0),
    (5, "5 zones", 210.0, 1939.0),
    (6, "All zones", 250.0, 2308.0),
]


def next_tuesday():
    """Choose a future Tuesday to reduce weekday/weekend differences."""
    today = date.today()
    days_until_tuesday = (1 - today.weekday()) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    return today + timedelta(days=days_until_tuesday)


def duration_to_minutes(value):
    """Convert the API duration '00d00:20:00' to 20.0 minutes."""
    match = re.fullmatch(r"(\d+)d(\d+):(\d+):(\d+)", str(value))
    if not match:
        raise ValueError(f"Unexpected duration format: {value!r}")
    days, hours, minutes, seconds = (int(piece) for piece in match.groups())
    return round(days * 1440 + hours * 60 + minutes + seconds / 60, 2)


def get_transport_times(station, travel_date):
    """Return travel times for up to four departures after 08:00."""
    response = requests.get(
        API_URL,
        params={
            "from": station,
            "to": DESTINATION,
            "date": travel_date,
            "time": COMMUTE_TIME,
            "limit": SAMPLE_LIMIT,
        },
        timeout=30,
    )
    response.raise_for_status()
    connections = response.json().get("connections", [])
    times = []
    for connection in connections:
        raw_duration = connection.get("duration")
        if raw_duration:
            try:
                times.append(duration_to_minutes(raw_duration))
            except ValueError as exc:
                print(f"   Skipped unexpected duration: {exc}")
    return times


def initialize_database(db):
    """Make two reusable tables. Existing data is preserved on reruns."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS commutes (
            municipality TEXT PRIMARY KEY,
            station TEXT NOT NULL,
            station_zone TEXT NOT NULL,
            route_zone_count INTEGER,
            destination TEXT NOT NULL,
            journey_date TEXT NOT NULL,
            departure_from TEXT NOT NULL,
            median_minutes REAL,
            fastest_minutes REAL,
            sampled_connections INTEGER NOT NULL,
            timing_source TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS zvv_pass_prices (
            tariff_level INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            monthly_chf REAL NOT NULL,
            annual_chf REAL NOT NULL,
            valid_from TEXT NOT NULL
        )
    """)
    db.executemany("""
        INSERT INTO zvv_pass_prices
            (tariff_level, label, monthly_chf, annual_chf, valid_from)
        VALUES (?, ?, ?, ?, '2025-12-14')
        ON CONFLICT(tariff_level) DO UPDATE SET
            label=excluded.label,
            monthly_chf=excluded.monthly_chf,
            annual_chf=excluded.annual_chf,
            valid_from=excluded.valid_from
    """, FARES)
    db.commit()


def read_municipalities():
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        raw = (row.get("route_zone_count") or "").strip()
        row["route_zone_count"] = int(raw) if raw else None
        if row["route_zone_count"] is not None and row["route_zone_count"] < 2:
            raise ValueError(f"Invalid route zone count for {row['municipality']}")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Build or update the transport database")
    parser.add_argument("--zones-only", action="store_true",
                        help="Update manually verified route zone counts without API calls")
    args = parser.parse_args()

    if args.zones_only:
        if not DATABASE.exists():
            print("Database missing. First run: python 02_build_database.py")
            return
        with sqlite3.connect(DATABASE) as db:
            for row in read_municipalities():
                db.execute(
                    "UPDATE commutes SET route_zone_count=? WHERE municipality=?",
                    (row["route_zone_count"], row["municipality"]),
                )
            db.commit()
        print("Updated zone counts from CSV without new transport API calls.")
        return

    journey_date = next_tuesday().isoformat()
    print(f"Collecting public transport times to {DESTINATION} on {journey_date} after {COMMUTE_TIME}.")
    print(f"SQLite database: {DATABASE}")

    municipalities = read_municipalities()
    with sqlite3.connect(DATABASE) as db:
        initialize_database(db)
        for row in municipalities:
            name = row["municipality"]
            station = row["station"]
            if station == DESTINATION:
                # It is the same station: no train trip is necessary.
                times = [0.0]
                source = "same station (assumption)"
            else:
                try:
                    times = get_transport_times(station, journey_date)
                    source = "transport.opendata.ch API"
                except (requests.RequestException, ValueError) as error:
                    print(f"WARNING - {name}: {error}")
                    times = []
                    source = "API unavailable"
                time.sleep(0.3)  # Small pause: avoid unnecessary API load.

            median = round(statistics.median(times), 1) if times else None
            fastest = min(times) if times else None
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            db.execute("""
                INSERT INTO commutes (
                    municipality, station, station_zone, route_zone_count,
                    destination, journey_date, departure_from, median_minutes,
                    fastest_minutes, sampled_connections, timing_source, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(municipality) DO UPDATE SET
                    station=excluded.station,
                    station_zone=excluded.station_zone,
                    route_zone_count=excluded.route_zone_count,
                    destination=excluded.destination,
                    journey_date=excluded.journey_date,
                    departure_from=excluded.departure_from,
                    median_minutes=excluded.median_minutes,
                    fastest_minutes=excluded.fastest_minutes,
                    sampled_connections=excluded.sampled_connections,
                    timing_source=excluded.timing_source,
                    recorded_at=excluded.recorded_at
            """, (
                name, station, row["station_zone"], row["route_zone_count"],
                DESTINATION, journey_date, COMMUTE_TIME, median, fastest,
                len(times), source, timestamp,
            ))
            db.commit()
            print(f"{name:14s} {str(median):>6s} min (n={len(times)}), route zones: {row['route_zone_count']}")

    print("\nDone. Run: python 03_view_database.py")
    print("Missing route zone counts are intentional: fill them using the official ZVV zone map.")


if __name__ == "__main__":
    main()
