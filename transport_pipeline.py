"""Lade Fahrzeiten und ZVV-Abopreise und speichere sie in SQLite.

Dieses Modul wird aus transport_steps.ipynb aufgerufen. Es liest die CSV-Dateien
im gleichen Ordner und speichert die Ergebnisse in transport.db.
"""

import csv  # Liest CSV-Tabellen wie municipalities.csv.
import sqlite3  # Erstellt und bearbeitet eine SQLite-Datenbank.
import time  # Erlaubt kurze Pausen zwischen den API-Anfragen.
from datetime import date, datetime, timedelta  # Arbeitet mit Datum und Uhrzeit.
from pathlib import Path  # Funktioniert mit Dateipfaden unter Windows/Mac.
from statistics import median  # Berechnet eine mittlere Fahrzeit.

import pandas as pd  # Zeigt Datenbank-Ergebnisse als Tabelle an.
import requests  # Ruft Daten aus dem Internet über eine API ab.

# In diesem Ordner befinden sich das Programm, die CSV-Dateien und die Datenbank.
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "transport.db"
MUNICIPALITIES_FILE = BASE_DIR / "municipalities.csv"
PRICES_FILE = BASE_DIR / "zvv_pass_prices.csv"
PT_API = "https://transport.opendata.ch/v1"
ORS_API = "https://api.openrouteservice.org/v2/directions"
SBB_CATALOG = "https://data.sbb.ch/api/explore/v2.1/catalog/datasets"


def next_tuesday():
    """Gib den nächsten Dienstag als YYYY-MM-DD zurück.

    Ein gleicher Werktag und eine gleiche Startzeit machen die Orte vergleichbar.
    """
    today = date.today()  # Heute bestimmen (Montag = 0, Dienstag = 1).
    days = (1 - today.weekday()) % 7  # Tage bis Dienstag berechnen.
    if days == 0:  # Falls heute Dienstag ist: nicht den heutigen Tag nehmen.
        days = 7
    return (today + timedelta(days=days)).isoformat()  # Z. B. 2026-11-17.


def fetch_pt_minutes(station, travel_date, trains_only=False):
    """Gib den Median von maximal vier ÖV-Verbindungen nach Zürich HB zurück."""
    params = {  # Die Suchparameter werden an die Transport-API geschickt.
        "from": station,  # Startbahnhof, zum Beispiel Winterthur.
        "to": "Zürich HB",  # Festes Ziel in eurem Projekt.
        "date": travel_date,  # Gleicher Werktag für alle Gemeinden.
        "time": "08:00",  # Suche nach Verbindungen ab 08:00 Uhr.
        "limit": 4,  # Maximal vier Verbindungsvorschläge abrufen.
    }
    if trains_only:  # Nur beim ersten Test ausschliesslich Züge abfragen.
        params["transportations"] = ["train"]
    answer = requests.get(f"{PT_API}/connections", params=params, timeout=30)
    answer.raise_for_status()  # Bei einem API-Fehler eine Fehlermeldung auslösen.
    connections = answer.json().get("connections", [])  # Antwort als JSON lesen.
    minutes = []  # Hier sammeln wir die Fahrtdauern der Verbindungen.
    for connection in connections:  # Jede gefundene Verbindung durchgehen.
        departure = connection.get("from", {}).get("departure")
        arrival = connection.get("to", {}).get("arrival")
        if departure and arrival:  # Nur vollständig gelieferte Zeiten verwenden.
            start = datetime.fromisoformat(departure)
            end = datetime.fromisoformat(arrival)
            duration = (end - start).total_seconds() / 60  # Sekunden -> Minuten.
            if duration >= 0:  # Negative Werte wären ein Datenfehler.
                minutes.append(duration)
    if not minutes:  # Keine Zeitangaben gefunden: Fehler statt Fantasiewert.
        raise ValueError(f"Keine auswertbare Verbindung für {station} gefunden.")
    return round(median(minutes), 1)  # Mittlere Fahrdauer in Minuten.


def fetch_station_coordinates(station):
    """Finde die GPS-Koordinaten eines Bahnhofs über die Transport-API.

    Die API liefert x = Breite und y = Länge. ORS erwartet die umgekehrte
    Reihenfolge [Längengrad, Breitengrad]; das erledigen wir erst bei der Route.
    """
    answer = requests.get(  # Startbahnhof in der Haltestellensuche finden.
        f"{PT_API}/locations",
        params={"query": station, "type": "station"},
        timeout=30,
    )
    answer.raise_for_status()  # HTTP-Fehler sichtbar machen.
    candidates = answer.json().get("stations", [])  # Haltestellenvorschläge.
    exact = next(  # Bevorzugt wird ein exakt gleich benannter Bahnhof.
        (item for item in candidates if item.get("name", "").casefold() == station.casefold()),
        None,
    )
    if exact is None:  # Keine unsichere Ortszuordnung automatisch übernehmen.
        raise ValueError(f"Bahnhof '{station}' nicht eindeutig gefunden.")
    coordinates = exact.get("coordinate") or {}  # Koordinaten des Bahnhofs.
    latitude = coordinates.get("x")  # x bedeutet hier Breitengrad.
    longitude = coordinates.get("y")  # y bedeutet hier Längengrad.
    if latitude is None or longitude is None:  # Keine Koordinaten vorhanden.
        raise ValueError(f"GPS-Koordinaten für '{station}' fehlen.")
    return float(latitude), float(longitude)


def init_database():
    """Erstelle die benötigten Datenbanktabellen, falls sie noch fehlen."""
    with sqlite3.connect(DB_FILE) as db:  # Verbindung zur SQLite-Datei öffnen.
        db.execute(  # Eine Zeile je Gemeinde; spätere App kann darauf zugreifen.
            """CREATE TABLE IF NOT EXISTS transport_data (
                   municipality TEXT PRIMARY KEY,
                   station TEXT NOT NULL,
                   station_zone INTEGER NOT NULL,
                   route_zone_count INTEGER,
                   pt_minutes REAL,
                   bike_minutes REAL,
                   car_minutes REAL,
                   bike_km REAL,
                   car_km REAL,
                   latitude REAL,
                   longitude REAL,
                   travel_date TEXT,
                   monthly_pass_chf REAL,
                   annual_pass_chf REAL
               )"""
        )
        db.execute(  # Eigenständige Preistabelle für den Tarif-Nachweis.
            """CREATE TABLE IF NOT EXISTS zvv_pass_prices (
                   fare_level INTEGER PRIMARY KEY,
                   monthly_chf REAL NOT NULL,
                   annual_chf REAL NOT NULL,
                   valid_from TEXT NOT NULL,
                   valid_until TEXT NOT NULL
               )"""
        )


def test_winterthur():
    """Teste den ersten API-Aufruf: Winterthur -> Zürich HB, nur Züge."""
    travel_date = next_tuesday()  # Für den Test einen künftigen Dienstag wählen.
    minutes = fetch_pt_minutes("Winterthur", travel_date, trains_only=True)
    print(f"Winterthur -> Zürich HB am {travel_date}: {minutes} Minuten (Median)")
    return minutes


def build_pt_database():
    """Lade die ÖV-Fahrzeit und Bahnhofslage aller 20 Gemeinden in SQLite."""
    init_database()  # Falls nötig, die Datenbank zuerst erstellen.
    travel_date = next_tuesday()  # Einheitliches Vergleichsdatum wählen.
    with MUNICIPALITIES_FILE.open(encoding="utf-8", newline="") as file:
        places = list(csv.DictReader(file))  # CSV-Zeilen als Wörterbücher lesen.
    with sqlite3.connect(DB_FILE) as db:  # Datenbank zum Schreiben öffnen.
        for place in places:  # Alle Gemeinden einzeln verarbeiten.
            name = place["municipality"]  # Gemeinde, z. B. Uster.
            station = place["station"]  # Abfahrtsbahnhof, z. B. Uster.
            zone = int(place["station_zone"])  # ZVV-Zone des Bahnhofs.
            entered = place["route_zone_count"].strip()  # Noch leere Zellen.
            paid_zones = int(entered) if entered else None  # Sonst Zahl.
            db.execute(  # Die Gemeinde aufnehmen, falls sie noch nicht existiert.
                """INSERT OR IGNORE INTO transport_data
                   (municipality, station, station_zone)
                   VALUES (?, ?, ?)""",
                (name, station, zone),
            )
            pt_minutes, latitude, longitude = None, None, None  # Standard: fehlt.
            try:  # API-Fehler sollen nicht das ganze Projekt abbrechen.
                pt_minutes = fetch_pt_minutes(station, travel_date)
                latitude, longitude = fetch_station_coordinates(station)
                print(f"OK: {name}: {pt_minutes} min")
            except (requests.RequestException, ValueError, KeyError) as error:
                print(f"FEHLER: {name}: {error}")  # Problem zur Prüfung ausgeben.
            db.execute(  # Verkehrsdaten aktualisieren; ORS-Ergebnisse bleiben erhalten.
                """UPDATE transport_data
                   SET station = ?, station_zone = ?, route_zone_count = ?,
                       pt_minutes = ?, latitude = ?, longitude = ?, travel_date = ?
                   WHERE municipality = ?""",
                (station, zone, paid_zones, pt_minutes,
                 latitude, longitude, travel_date, name),
            )
            db.commit()  # Das Ergebnis dieser Gemeinde sofort speichern.
            time.sleep(0.3)  # API nicht mit zu vielen Anfragen belasten.
    print(f"Fertig. Datenbankdatei: {DB_FILE}")


def research_sbb_prices():
    """Suche im SBB-Open-Data-Katalog nach Tarif-Datensätzen.

    Nur eine Recherche: Die Suchresultate sind keine ZVV-Abopreise.
    """
    for term in ("tarif", "preis", "fare"):  # Drei Begriffe untersuchen.
        try:
            response = requests.get(  # Den öffentlichen SBB-Datenkatalog anfragen.
                SBB_CATALOG,
                params={"search": term, "limit": 5},
                timeout=30,
            )
            response.raise_for_status()  # API-Fehler erkennen.
            data = response.json()  # JSON-Antwort lesen.
            results = data.get("results", [])  # Liste gefundener Datensätze.
            print(f"\nSuche nach '{term}': {len(results)} Treffer in dieser Antwort")
            for item in results:  # Titel und Datensatz-ID ausgeben.
                title = item.get("metas", {}).get("default", {}).get("title", "Ohne Titel")
                print("-", item.get("dataset_id", "?"), ":", title)
        except (requests.RequestException, ValueError) as error:
            print(f"SBB-Recherche für '{term}' fehlgeschlagen: {error}")
        time.sleep(0.3)  # Kleine Pause zwischen den Suchen.


def update_pass_prices():
    """Lade die offizielle manuelle Preistabelle und ordne Preise zu.

    Ohne geprüfte route_zone_count bleibt der Preis bewusst NULL.
    """
    init_database()  # Preise bekommen eine eigene Datenbanktabelle.
    with PRICES_FILE.open(encoding="utf-8", newline="") as file:
        price_rows = list(csv.DictReader(file))  # ZVV-Preis-CSV einlesen.
    with MUNICIPALITIES_FILE.open(encoding="utf-8", newline="") as file:
        municipalities = list(csv.DictReader(file))  # Geprüfte Streckenzonen.
    prices = {}  # Abbildung: Tarifstufe -> Monats- und Jahrespreis.
    with sqlite3.connect(DB_FILE) as db:
        db.execute("DELETE FROM zvv_pass_prices")  # Alte Tarif-Tabelle ersetzen.
        for row in price_rows:  # Jede der fünf Tarifstufen erfassen.
            level = int(row["fare_level"])
            monthly = float(row["monthly_chf"])
            annual = float(row["annual_chf"])
            prices[level] = (monthly, annual)  # Zur späteren Zuordnung merken.
            db.execute(  # Tarifinformationen samt Gültigkeitsdatum speichern.
                """INSERT INTO zvv_pass_prices
                   (fare_level, monthly_chf, annual_chf, valid_from, valid_until)
                   VALUES (?, ?, ?, ?, ?)""",
                (level, monthly, annual, row["valid_from"], row["valid_until"]),
            )
        for place in municipalities:  # Für jede Gemeinde die Preisstufe suchen.
            value = place["route_zone_count"].strip()  # Geprüfte Streckenzonen.
            zone_count = int(value) if value else None  # Unbekannt bleibt NULL.
            if zone_count is not None and zone_count < 2:
                raise ValueError("Eine Fahrt nach Zürich HB braucht mindestens 2 Tarifzonen.")
            fare_level = min(zone_count, 6) if zone_count is not None else None
            monthly, annual = prices[fare_level] if fare_level is not None else (None, None)
            db.execute(  # Nur Preis und Streckenzonen aktualisieren.
                """UPDATE transport_data
                   SET route_zone_count = ?, monthly_pass_chf = ?, annual_pass_chf = ?
                   WHERE municipality = ?""",
                (zone_count, monthly, annual, place["municipality"]),
            )
        db.commit()  # Änderungen in transport.db speichern.
    print("ZVV-Preistabelle aktualisiert. Fehlende Streckenzonen bleiben leer.")


def fetch_ors_route(profile, start_lat, start_lon, end_lat, end_lon, api_key):
    """Liefere Dauer (Minuten) und Strecke (km) für Fahrrad oder Auto."""
    response = requests.post(  # OpenRouteService via POST ansprechen.
        f"{ORS_API}/{profile}/json",  # Fahrrad oder Auto auswählen.
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={  # ORS erwartet Koordinaten als [Längengrad, Breitengrad].
            "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        },
        timeout=45,
    )
    response.raise_for_status()  # Ungültige Keys und andere API-Fehler anzeigen.
    summary = response.json()["routes"][0]["summary"]  # Erste Route.
    minutes = round(summary["duration"] / 60, 1)  # Sekunden -> Minuten.
    kilometres = round(summary["distance"] / 1000, 1)  # Meter -> km.
    return minutes, kilometres


def add_bike_car_times(api_key):
    """Ergänze die vorhandene Datenbank um Rad- und Autofahrzeiten.

    Ein gültiger ORS-Key ist erforderlich. Station zu Zürich HB, nicht Wohnung
    zu Bürotür. Autowerte sind ohne aktuelle Staus und ohne Parkplatzsuche.
    """
    if not api_key.strip():  # Einen leeren API-Key nicht akzeptieren.
        raise ValueError("Bitte einen gültigen OpenRouteService API-Key angeben.")
    init_database()  # Datenbank muss vorhanden sein.
    end_lat, end_lon = fetch_station_coordinates("Zürich HB")  # Zielkoordinaten.
    with sqlite3.connect(DB_FILE) as db:  # Verbindung zur Datenbank öffnen.
        db.row_factory = sqlite3.Row  # Datensätze über Spaltennamen lesbar machen.
        places = db.execute(  # Nur Gemeinden mit bekannten Startkoordinaten laden.
            """SELECT municipality, latitude, longitude FROM transport_data
               WHERE latitude IS NOT NULL AND longitude IS NOT NULL"""
        ).fetchall()
        for place in places:  # Alle verfügbaren Gemeinden verarbeiten.
            for profile, label in (("cycling-regular", "bike"), ("driving-car", "car")):
                try:  # Ein einzelner Routing-Fehler stoppt nicht alle Gemeinden.
                    minutes, kilometres = fetch_ors_route(
                        profile, place["latitude"], place["longitude"],
                        end_lat, end_lon, api_key,
                    )
                    # Spaltennamen sind hier fest vorgegeben, nicht vom Nutzer.
                    db.execute(  # Minuten und Kilometer für diesen Modus speichern.
                        f"UPDATE transport_data SET {label}_minutes = ?, {label}_km = ? WHERE municipality = ?",
                        (minutes, kilometres, place["municipality"]),
                    )
                    db.commit()  # Je Route speichern, damit kein Resultat verloren geht.
                    print(f"OK: {place['municipality']} - {label}: {minutes} min")
                except (requests.RequestException, KeyError, IndexError, ValueError) as error:
                    print(f"FEHLER: {place['municipality']} - {label}: {error}")
                time.sleep(0.3)  # Rücksicht auf die API-Nutzungslimits.
    print("Fahrrad- und Autodaten ergänzt, soweit die API sie liefern konnte.")


def show_database():
    """Zeige den Transport-Datensatz der späteren Streamlit-App."""
    init_database()  # Tabellen erstellen, falls das Notebook zuerst hier startet.
    with sqlite3.connect(DB_FILE) as db:
        table = pd.read_sql_query(  # Daten aus SQLite in eine pandas-Tabelle laden.
            """SELECT municipality, station_zone, route_zone_count,
                      pt_minutes, bike_minutes, car_minutes,
                      monthly_pass_chf, annual_pass_chf, travel_date
               FROM transport_data ORDER BY municipality""",
            db,
        )
    return table  # Jupyter stellt den Rückgabewert als Tabelle dar.
