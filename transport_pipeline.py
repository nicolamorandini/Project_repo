"""Ermittle Pendelzeiten und ZVV-Abopreise fuer 1. und 2. Klasse.

Alle Dateien liegen DIREKT im Hauptverzeichnis des GitHub-Repositories.
Die CSV-Dateien koennen z. B. 'municapilites.csv' und 'zvv_passes.csv'
heissen. Die Ergebnisse werden daneben in 'transport.db' gespeichert.
"""

import csv  # Liest CSV-Tabellen wie municipalities.csv.
import sqlite3  # Erstellt und bearbeitet eine SQLite-Datenbank.
import time  # Erlaubt kurze Pausen zwischen den API-Anfragen.
from datetime import date, datetime, timedelta  # Arbeitet mit Datum und Uhrzeit.
from pathlib import Path  # Funktioniert mit Dateipfaden unter Windows/Mac.
from statistics import median  # Berechnet eine mittlere Fahrzeit.

import pandas as pd  # Zeigt Datenbank-Ergebnisse als Tabelle an.
import requests  # Ruft Daten aus dem Internet über eine API ab.

# Das Python-Programm, Notebook, CSV-Dateien und transport.db liegen in main.
# Der Ort der Python-Datei ist verlaesslicher als das wechselnde Jupyter-Verzeichnis.
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "transport.db"

# Beide Schreibweisen werden unterstuetzt, auch ohne die Endung .csv.
# Die zuerst gefundene Datei wird verwendet; existierende Daten bleiben unangetastet.
MUNICIPALITY_NAMES = (
    "municapilites.csv", "municipalities.csv", "municipalites.csv",
    "municapilites", "municipalities", "municipalites",
)
PRICE_NAMES = (
    "zvv_passes.csv", "zvv_pass_prices.csv", "zvv_passes", "zvv_pass_prices",
)


def find_existing_file(possible_names):
    """Suche CSV-Dateien im selben Ordner wie dieses Python-Programm.

    Bei fehlender Datei entsteht eine aussagekraeftige Fehlermeldung.
    """
    # Erst vorhandene Dateinamen einsammeln; das erlaubt Gross-/Kleinschreibung.
    existing = {path.name.casefold(): path for path in BASE_DIR.iterdir() if path.is_file()}
    for name in possible_names:  # Bekannte Schreibweisen durchprobieren.
        if name.casefold() in existing:
            return existing[name.casefold()]
    candidates = ", ".join(possible_names)
    raise FileNotFoundError(
        f"Keine passende CSV-Datei gefunden im Ordner: {BASE_DIR}\n"
        f"Gesuchte Dateinamen: {candidates}\n"
        "Lege die bestehende CSV neben transport_pipeline.py in das GitHub-Hauptverzeichnis."
    )


def read_csv_rows(file_path, required_columns):
    """Lies CSV mit Komma oder Semikolon und kontrolliere die Spaltennamen."""
    with file_path.open(encoding="utf-8-sig", newline="") as file:
        sample = file.read(2048)  # Kleiner Textausschnitt fuer die Trennzeichenerkennung.
        file.seek(0)  # Wieder am Dateianfang beginnen.
        delimiter = ";" if sample.splitlines()[0].count(";") > sample.splitlines()[0].count(",") else ","
        reader = csv.DictReader(file, delimiter=delimiter)
        headers = [name.strip() for name in (reader.fieldnames or [])]
        missing = sorted(set(required_columns) - set(headers))
        if missing:
            raise ValueError(
                f"Die Datei '{file_path.name}' enthaelt nicht die Spalten {missing}.\n"
                f"Vorhandene Spalten: {headers}. Bitte zuerst die CSV-Kopfzeile pruefen."
            )
        rows = [{(key or "").strip(): (value or "").strip()
                 for key, value in row.items()} for row in reader]
    return rows


# Dateipfade erst dann ermitteln, wenn eine Funktion die jeweilige CSV braucht.
# Dadurch funktioniert z. B. der Winterthur-Test auch vor dem CSV-Upload.
def municipality_file():
    """Liefere den wirklichen Dateipfad der Gemeinde-CSV in main."""
    return find_existing_file(MUNICIPALITY_NAMES)


def prices_file():
    """Liefere den wirklichen Dateipfad der ZVV-Preis-CSV in main."""
    return find_existing_file(PRICE_NAMES)


def check_input_files():
    """Zeige in Jupyter, welche Dateien erkannt werden und ob Spalten fehlen."""
    print("Projektordner:", BASE_DIR)
    places = municipality_file()
    prices = prices_file()
    print("Gemeindeliste:", places.name)
    print("ZVV-Preise:  ", prices.name)
    place_rows = read_csv_rows(
        places, ("municipality", "station", "station_zone", "route_zone_count")
    )
    price_rows = read_csv_rows(
        prices, ("fare_level", "fare_class", "monthly_chf", "annual_chf",
                 "valid_from", "valid_until", "source_url")
    )
    print(f"Gemeinden: {len(place_rows)} | Tarifzeilen: {len(price_rows)}")
    print("Dateipfade und Spalten: OK")
    return places, prices


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
        # Falls eine alte Datenbank nur Preise fuer die 2. Klasse enthaelt,
        # ersetzen wir ausschliesslich deren alte Tariftabelle. Die Reisezeiten
        # in transport_data bleiben unveraendert.
        price_columns = {row[1] for row in db.execute("PRAGMA table_info(zvv_pass_prices)")}
        if price_columns and "fare_class" not in price_columns:
            db.execute("DROP TABLE zvv_pass_prices")

        db.execute(  # Offizielle Tarife: eine Zeile je Tarifstufe UND Klasse.
            """CREATE TABLE IF NOT EXISTS zvv_pass_prices (
                   fare_level INTEGER NOT NULL,
                   fare_class INTEGER NOT NULL CHECK (fare_class IN (1, 2)),
                   monthly_chf REAL NOT NULL,
                   annual_chf REAL NOT NULL,
                   valid_from TEXT NOT NULL,
                   valid_until TEXT NOT NULL,
                   source_url TEXT NOT NULL,
                   PRIMARY KEY (fare_level, fare_class)
               )"""
        )
        db.execute(  # Preise je Gemeinde und Klasse getrennt speichern.
            """CREATE TABLE IF NOT EXISTS municipality_pass_prices (
                   municipality TEXT NOT NULL,
                   fare_class INTEGER NOT NULL CHECK (fare_class IN (1, 2)),
                   fare_level INTEGER NOT NULL,
                   monthly_chf REAL NOT NULL,
                   annual_chf REAL NOT NULL,
                   PRIMARY KEY (municipality, fare_class)
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
    places = read_csv_rows(  # Echte CSV im GitHub-Hauptordner finden und einlesen.
        municipality_file(),
        ("municipality", "station", "station_zone", "route_zone_count"),
    )
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
            pt_minutes, latitude, longitude = None, None, None  # Fehlend bleibt leer.
            try:  # Fahrzeit separat versuchen.
                pt_minutes = fetch_pt_minutes(station, travel_date)
                print(f"OK: {name}: {pt_minutes} min")
            except (requests.RequestException, ValueError, KeyError) as error:
                print(f"FEHLER (OeV): {name}: {error}")
            try:  # Koordinaten separat versuchen: ein Fehler loescht keine Fahrzeit.
                latitude, longitude = fetch_station_coordinates(station)
            except (requests.RequestException, ValueError, KeyError) as error:
                print(f"FEHLER (Koordinaten): {name}: {error}")
            db.execute(  # Bereits vorhandene Werte nicht durch NULL ueberschreiben.
                """UPDATE transport_data
                   SET station = ?, station_zone = ?, route_zone_count = ?,
                       pt_minutes = COALESCE(?, pt_minutes),
                       latitude = COALESCE(?, latitude),
                       longitude = COALESCE(?, longitude),
                       travel_date = CASE WHEN ? IS NOT NULL THEN ? ELSE travel_date END
                   WHERE municipality = ?""",
                (station, zone, paid_zones, pt_minutes, latitude, longitude,
                 pt_minutes, travel_date, name),
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
    """Speichere ZVV-Abopreise fuer BEIDE Klassen in SQLite.

    Die Auswahl 1./2. Klasse erfolgt spaeter mit show_database(fare_class=...).
    So kann jede Person die Klasse selbst waehlen, ohne transport.db umzuschreiben.
    Ohne gepruefte route_zone_count bleibt der Gemeindepreis unbekannt (NULL).
    """
    init_database()  # Neue Tabellen anlegen; alte Datenbanken ggf. migrieren.
    price_rows = read_csv_rows(  # CSV-Tarife beider Klassen aus main lesen.
        prices_file(),
        ("fare_level", "fare_class", "monthly_chf", "annual_chf",
         "valid_from", "valid_until", "source_url"),
    )
    municipalities = read_csv_rows(  # Gemeinden aus derselben Repo-Ebene lesen.
        municipality_file(),
        ("municipality", "station", "station_zone", "route_zone_count"),
    )

    prices = {}  # Schluessel (Tarifstufe, Klasse) -> (Monats-, Jahrespreis).
    for row in price_rows:  # Jede Tabellenzeile auf Plausibilitaet pruefen.
        level = int(row["fare_level"])  # Beispiel: 3 Zonen.
        fare_class = int(row["fare_class"])  # Entweder 1 oder 2.
        monthly = float(row["monthly_chf"])  # Preis fuer ein Monatsabo.
        annual = float(row["annual_chf"])  # Preis fuer ein Jahresabo.
        if level not in (2, 3, 4, 5, 6) or fare_class not in (1, 2):
            raise ValueError(f"Ungueltige Tarifstufe oder Klasse: {row}")
        if monthly <= 0 or annual <= 0:
            raise ValueError(f"Preise muessen positiv sein: {row}")
        if (level, fare_class) in prices:
            raise ValueError(f"Doppelter Tarif fuer Stufe {level}, Klasse {fare_class}")
        prices[level, fare_class] = (monthly, annual)  # Zur Zuordnung merken.

    # Jede Tarifstufe muss in beiden Klassen vorkommen.
    required = {(level, fare_class) for level in range(2, 7) for fare_class in (1, 2)}
    if set(prices) != required:
        raise ValueError(f"Preistabelle unvollstaendig. Es fehlen: {required - set(prices)}")

    with sqlite3.connect(DB_FILE) as db:  # Alle Aenderungen gemeinsam speichern.
        db.execute("DELETE FROM municipality_pass_prices")  # Alte Zuordnungen leeren.
        db.execute("DELETE FROM zvv_pass_prices")  # Alte Tarifzeilen ersetzen.
        for row in price_rows:  # Zehn Zeilen: 5 Preisstufen x 2 Klassen.
            db.execute(
                """INSERT INTO zvv_pass_prices
                   (fare_level, fare_class, monthly_chf, annual_chf,
                    valid_from, valid_until, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (int(row["fare_level"]), int(row["fare_class"]),
                 float(row["monthly_chf"]), float(row["annual_chf"]),
                 row["valid_from"], row["valid_until"], row["source_url"]),
            )

        for place in municipalities:  # Jede Gemeinde einmal verarbeiten.
            name = place["municipality"]  # Beispiel: Winterthur.
            zone = int(place["station_zone"])  # Zone des Ausgangsbahnhofs.
            value = place["route_zone_count"].strip()  # Verifizierte Zahl oder leer.
            zone_count = int(value) if value else None  # Leer bleibt unbekannt.
            if zone_count is not None and zone_count < 2:
                raise ValueError(f"Mindestens 2 verrechnete Zonen erforderlich: {name}")
            fare_level = min(zone_count, 6) if zone_count is not None else None

            # Falls die Fahrzeit-API noch nicht ausgefuehrt wurde, trotzdem Ort anlegen.
            db.execute(
                """INSERT OR IGNORE INTO transport_data
                   (municipality, station, station_zone) VALUES (?, ?, ?)""",
                (name, place["station"], zone),
            )

            # Bestehende Spalten bleiben kompatibel: die Standardwerte sind
            # weiterhin die 2. Klasse. Die 1. Klasse liegt in der neuen Tabelle.
            second_monthly, second_annual = (
                prices[fare_level, 2] if fare_level is not None else (None, None)
            )
            db.execute(
                """UPDATE transport_data SET station = ?, station_zone = ?,
                   route_zone_count = ?, monthly_pass_chf = ?, annual_pass_chf = ?
                   WHERE municipality = ?""",
                (place["station"], zone, zone_count,
                 second_monthly, second_annual, name),
            )
            if fare_level is None:  # Keine Streckenzonen -> keinen Preis erfinden.
                continue
            for fare_class in (1, 2):  # Fuer beide Klassen den Preis speichern.
                monthly, annual = prices[fare_level, fare_class]
                db.execute(
                    """INSERT INTO municipality_pass_prices
                       (municipality, fare_class, fare_level, monthly_chf, annual_chf)
                       VALUES (?, ?, ?, ?, ?)""",
                    (name, fare_class, fare_level, monthly, annual),
                )
    print("ZVV-Preise fuer 1. und 2. Klasse gespeichert. Ungepruefte Zonen bleiben leer.")


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


def show_database(fare_class=2):
    """Zeige Fahrzeiten und Abopreise fuer die gewaehlte OeV-Klasse an.

    Args:
        fare_class: 1 fuer die 1. Klasse oder 2 fuer die 2. Klasse (Standard).

    Returns:
        pandas.DataFrame mit den Fahrzeiten und passenden Monats-/Jahrespreisen.

    Beispiel: show_database(fare_class=1) zeigt nur die Preise 1. Klasse.
    """
    if fare_class not in (1, 2):  # Ungueltige Eingaben bewusst ablehnen.
        raise ValueError("fare_class muss 1 oder 2 sein.")
    init_database()  # Tabellen erstellen, falls das Notebook zuerst hier startet.
    with sqlite3.connect(DB_FILE) as db:
        table = pd.read_sql_query(  # Preise ueber eine zweite Tabelle passend laden.
            """SELECT t.municipality, t.station_zone, t.route_zone_count,
                      t.pt_minutes, t.bike_minutes, t.car_minutes,
                      p.monthly_chf AS monthly_pass_chf,
                      p.annual_chf AS annual_pass_chf,
                      ? AS fare_class, t.travel_date
               FROM transport_data AS t
               LEFT JOIN municipality_pass_prices AS p
                 ON p.municipality = t.municipality AND p.fare_class = ?
               ORDER BY t.municipality""",
            db,
            params=(fare_class, fare_class),  # Werte sicher ins SQL uebergeben.
        )
    return table  # Diese Tabelle kann auch Streamlit direkt verwenden.
