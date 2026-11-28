"""Integration checks. AI assistance: ChatGPT, 2026-11-28."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import numpy as np
import pandas as pd
from real_data import BASE, load_listings, predict_rents, load_transport

class IntegrationTests(unittest.TestCase):
    def test_real_snapshot_and_notebook_prediction_units(self):
        listings = load_listings()
        csv = pd.read_csv(BASE / 'data/flatfox_zurich.csv')
        self.assertEqual(set(listings.id), set(csv.id))
        result, meta = predict_rents(listings)
        self.assertEqual(meta['year_median'], 2012.0)
        self.assertAlmostEqual(meta['mae'], 530.0056633443955, places=5)
        self.assertTrue(np.isfinite(result.fair_rent).all())
        self.assertTrue((result.fair_rent > 0).all())
        self.assertEqual(result.model_training_listing.sum(), 942)

    def test_missing_routes_are_not_zero_and_annual_prices(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            for name in ['municipalities.csv', 'zvv_pass_prices.csv']:
                shutil.copy(BASE / name, base / name)
            monthly = load_transport(base, today='2026-11-28')
            annual = load_transport(base, annual=True, today='2026-11-28')
            self.assertTrue(monthly.pt_minutes.isna().all())
            self.assertFalse((base / 'transport.db').exists())
            self.assertTrue(np.allclose(annual.transport_monthly, annual.annual_chf / 12))
            expired = load_transport(base, today='2030-01-01')
            self.assertTrue(expired.transport_monthly.isna().all())

    def test_streamlit_renders_and_vehicle_missing_input_is_explicit(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(BASE / 'app.py')).run(timeout=60)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        mode = next(x for x in app.selectbox if x.label == 'Transport mode')
        mode.select('Car').run(timeout=60)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertTrue(any('Complete all vehicle inputs' in x.value for x in app.info))
        for control in app.number_input:
            if control.value is None:
                control.set_value(0.0)
        app.run(timeout=60)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertTrue(any(x.label == 'Total including time' for x in app.metric))

if __name__ == '__main__':
    unittest.main()
