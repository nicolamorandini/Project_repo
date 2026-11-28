"""Real listing/model adapters. AI assistance: ChatGPT, 2026-11-28."""
from pathlib import Path
import sqlite3
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

BASE = Path(__file__).resolve().parent
FEATURES = ['rooms', 'surface_m2', 'year_built', 'year_missing', 'lat', 'lon']


def load_listings(base=BASE):
    """Read Paul's SQLite snapshot; never substitute the synthetic test CSV."""
    path = base / 'data/wohnungen.db'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        df = pd.read_sql_query('SELECT * FROM listings', conn)
    required = ['id', 'municipality', 'rooms', 'surface_m2', 'year_built', 'lat', 'lon', 'rent_gross', 'url']
    if not set(required).issubset(df.columns):
        raise ValueError('The listings table does not have the expected Flatfox columns.')
    for name in ['rooms', 'surface_m2', 'year_built', 'lat', 'lon', 'rent_gross']:
        df[name] = pd.to_numeric(df[name], errors='coerce')
    numeric = df[['rooms', 'surface_m2', 'lat', 'lon', 'rent_gross']]
    valid = np.isfinite(numeric).all(axis=1) & (df['rooms'] > 0) & (df['surface_m2'] > 0) & (df['rent_gross'] > 0)
    df = df.loc[valid].drop_duplicates('id').copy()
    df['municipality'] = df['municipality'].str.strip().replace({'Zurich': 'Zürich'})
    return df


def model_features(df, median):
    """Reproduce Nicola's feature order and training-only year imputation."""
    x = df.copy()
    x['year_missing'] = x['year_built'].isna().astype(int)
    x['year_built'] = x['year_built'].fillna(median)
    return x[FEATURES]


def predict_rents(listings, base=BASE):
    """Use the saved model, whose output is gross CHF/m², not monthly CHF.

    The notebook did not export preprocessing metadata. Reconstruct its
    exact split from its original CSV to recover the training median and MAE.
    This must be revised together with any future model/training-data update.
    """
    source = pd.read_csv(base / 'data/flatfox_zurich.csv')
    source = source[(source.rent_gross / source.surface_m2).between(10, 80)].copy()
    train, test = train_test_split(source, test_size=0.3, random_state=1)
    median = train.year_built.median()
    with warnings.catch_warnings():
        warnings.simplefilter('error', InconsistentVersionWarning)
        model = joblib.load(base / 'model.joblib')
    if list(model.feature_names_in_) != FEATURES:
        raise ValueError('Model features differ from the ML notebook; update the adapter.')
    test_predictions = model.predict(model_features(test, median)) * test.surface_m2
    mae = float(mean_absolute_error(test.rent_gross, test_predictions))
    result = listings.copy()
    result['fair_rent'] = model.predict(model_features(result, median)) * result.surface_m2
    result['model_training_listing'] = result.id.isin(train.id)
    gap = result.rent_gross - result.fair_rent
    result['verdict'] = np.select([gap < -mae, gap > mae], ['Underpriced', 'Overpriced'], default='Within model error')
    return result, {'year_median': float(median), 'mae': mae, 'test_count': len(test)}


def load_transport(base=BASE, fare_class=2, annual=False, today=None):
    """Join the team's route-zone CSV and valid tariff rows; preserve missing times."""
    today = pd.Timestamp(today or pd.Timestamp.today().date())
    places = pd.read_csv(base / 'municipalities.csv')
    prices = pd.read_csv(base / 'zvv_pass_prices.csv')
    prices = prices[(prices.fare_class == fare_class) &
                    (pd.to_datetime(prices.valid_from) <= today) &
                    (pd.to_datetime(prices.valid_until) >= today)].copy()
    places['fare_level'] = places.route_zone_count.clip(upper=6)
    result = places.merge(prices, on='fare_level', how='left', validate='many_to_one')
    result['transport_monthly'] = result.annual_chf / 12 if annual else result.monthly_chf
    columns = ['municipality', 'pt_minutes', 'bike_minutes', 'car_minutes', 'bike_km', 'car_km', 'travel_date']
    path = base / 'transport.db'
    if path.exists():
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
            times = pd.read_sql_query('SELECT ' + ','.join(columns) + ' FROM transport_data', conn)
        result = result.merge(times, on='municipality', how='left', validate='one_to_one')
    else:
        for col in columns[1:]:
            result[col] = np.nan
    return result
