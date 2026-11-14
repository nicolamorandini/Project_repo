"""Step 1: Retrieve train connections Winterthur -> Zürich HB."""
from datetime import date, timedelta
import requests

API_URL = "https://transport.opendata.ch/v1/connections"


def next_tuesday():
    """Choose the next Tuesday to compare regular weekday commuting."""
    today = date.today()
    days_until_tuesday = (1 - today.weekday()) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    return today + timedelta(days=days_until_tuesday)


def main():
    query_date = next_tuesday().isoformat()
    params = {
        "from": "Winterthur",
        "to": "Zürich HB",
        "date": query_date,
        "time": "08:00",
        "limit": 4,
        "transportations[]": "train",  # Only train services for this first test.
    }

    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()  # Reports e.g. HTTP 404/500 errors.
        connections = response.json().get("connections", [])
    except (requests.RequestException, ValueError) as error:
        print("API request failed:", error)
        return

    print(f"Train connections: Winterthur -> Zürich HB on {query_date}")
    if not connections:
        print("No connections were returned. Check station names and API availability.")
        return

    for item in connections:
        departure = item.get("from", {}).get("departure", "unknown")
        arrival = item.get("to", {}).get("arrival", "unknown")
        duration = item.get("duration", "unknown")
        print(f"Departure: {departure} | Arrival: {arrival} | Duration: {duration}")


if __name__ == "__main__":
    main()
