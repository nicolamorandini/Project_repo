# Where Should I Live?

University of St. Gallen — FCS Group Project 07.01

## Project idea

We are developing an app to help people working near Zürich HB compare
apartments in the ZVV area.

The planned app compares:
- Actual rent.
- Public transport pass costs.
- Commuting time valued using the user's salary.
- Actual rent versus a predicted fair-rent benchmark.

The aim is to show how a cheaper apartment can become less attractive
once transport costs and commuting time are considered.

## Current status — real-data integration, 28 November 2026

The app now reads 1,411 real Flatfox listings from `data/wohnungen.db`,
uses Nicola's saved `model.joblib` for gross fair-rent predictions, and
joins municipality transport data and tariff CSVs. It never reads
`data/test_listings.csv` or inserts fictional listing/route values.

The model predicts CHF/m²; `real_data.py` multiplies by living area.
It reproduces the notebook's original training/test split to recover the
training year median (2012) and held-out MAE (CHF 530.01). Training listings
are labelled; their predictions are not independent valuations. The
notebook/model/original training CSV must be updated together. Ideally,
the ML owner should export a preprocessing pipeline and evaluation metadata.

Public transport ranking excludes listings without a matching route or
currently valid tariff. The supplied municipality list does not cover all
listing locations (including Zürich itself). Locations are matched exactly;
we do not invent zones or map neighbourhoods to municipalities automatically.
Travel times are station-to-HB, not apartment-to-office. Timetable dates
are displayed. Refresh transport data as needed; listings are snapshots.

Bike/car route columns are read when available. Motorbike routes, missing
bike/car routes and vehicle ownership costs must be entered by the user.
There are no fictional vehicle price defaults. Full vehicle ownership costs
include depreciation, so they must not be described as cash bills.

### Run the integrated app

Use Python 3.12. The saved scikit-learn 1.9.0 model needs a newer environment
than the original Python 3.9 cost demo. Do not reuse that old environment.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

A Python 3.12 environment is already prepared in Jordi's `integrated_project`
folder. From that folder, run `.venv/bin/python -m streamlit run app.py`.

### Refresh public transport data

```bash
python -c "from transport_pipeline import build_pt_database, update_pass_prices; build_pt_database(); update_pass_prices()"
```

Internet access is required. Route failures remain missing. Tariffs come
from the team's CSV, with its source URLs and validity dates; updating the
route database does not fetch newer tariffs automatically.

### Validate

```bash
python -m unittest -v test_costs test_real_data
```

Integration checks cover the actual listing/model snapshot, notebook MAE,
missing routes, expired prices, annual pass conversion and Streamlit mode changes.

## Repository files

| File | Purpose |
| --- | --- |
| app.py | Real listing filters, public transport ranking and vehicle cost details |
| real_data.py | SQLite, ML preprocessing/predictions and transport joins |
| requirements.txt | Tested dependencies for Python 3.12 |
| transport.db | Collected route-time snapshot |
| costs.py | Monthly cost, hourly time value and ranking functions |
| example.py | Demonstrates the calculations with fictional inputs |
| test_costs.py | Nine automated checks for the cost functions |
| municipalities.csv | Municipality and transport-zone inputs |
| zvv_pass_prices.csv | Transport tariff inputs |
| transport_pipeline.py | Collects travel data and stores it in SQLite |
| transport_steps.ipynb | Notebook for the transport workflow |

## Setup

1. Install Python 3 and GitHub Desktop.
2. Clone https://github.com/nicolamorandini/Project_repo.
3. Open the cloned Project_repo folder in VS Code.
4. Open Terminal → New Terminal.

The cost example and cost tests use only Python's standard library.
No additional packages are needed to run them.

## Run the cost example

From the Project_repo folder:

```bash
python3 example.py
```

The output separates:
- Monthly rent and transport spending.
- Monthly commuting hours.
- The monetary value assigned to commuting time.
- Total monthly cost including time.
- Fair-rent preference scores.

The example uses fictional inputs, not real apartment or tariff data.
Changing the inputs in example.py changes the results.

## Run the cost tests

```bash
python3 -m unittest -v test_costs
```

Expected result: nine tests pass, ending with OK.

The tests cover the worked example, annual-pass conversion, remote
working, zero time valuation, invalid inputs and ranking behaviour.

## Cost calculation

All monetary amounts are in CHF.

```text
Monthly commuting hours =
2 × one-way commuting minutes × office days per month / 60

Monthly time cost =
monthly commuting hours × hourly time value

Monthly cash cost =
actual monthly rent including charges + monthly transport cost

Total monthly cost including time =
monthly cash cost + monthly time cost
```

An annual pass is converted to a monthly equivalent by dividing its
price by 12.

The salary-based estimate is:

```text
Hourly time value =
annual salary / (52 × weekly working hours) × time-value fraction
```

Annual salary should include any 13th salary payment.
The time-value fraction ranges from 0 to 1.

The value of commuting time is a modelling assumption.
It is not an additional bill paid by the user.

## Fair-rent ranking score

```text
Score =
total monthly cost + p × (actual monthly rent − predicted fair rent)
```

Lower scores rank first.

- p = 0: rank only by total monthly cost.
- p > 0: additionally reward underpricing and penalise overpricing.

This score is not an expense. Cash costs and the ranking score should
be displayed separately.

Actual and predicted rents must use the same basis: both including
charges or both excluding charges. The user's rent budget should be
applied before ranking.

Fair-rent predictions use the saved model from the ML workstream.

## Transport workflow

The transport pipeline requires pandas and requests. In an activated
Python virtual environment, install them with:

```bash
python3 -m pip install pandas requests
```

The following commands check the input files, collect public transport
data and import the pass prices:

```bash
python3 -c "from transport_pipeline import check_input_files; check_input_files()"
python3 -c "from transport_pipeline import build_pt_database; build_pt_database()"
python3 -c "from transport_pipeline import update_pass_prices; update_pass_prices()"
```

Run these commands from the repository root. They create or update
transport.db. Travel-data collection requires an internet connection.

These transport commands have not been validated as part of the
cost-module tests.

## Data sources and limitations

Project sources:
- Flatfox public API for apartment listings.
- transport.opendata.ch for public transport travel times.
- Official ZVV/SBB information for transport tariffs.

The transport workflow measures journeys from a municipality's station
to Zürich HB. It does not yet include the apartment-to-station journey.

Missing travel times or prices must not be treated as zero.
Tariff validity and route-zone counts need verification.

Predicted fair rent is a statistical benchmark, not a guarantee of
an apartment's true value.

Municipal taxes and additional transport modes are optional extensions.

## Team responsibilities

- Paul Berkmann: rent data.
- Jan-Nicklas Bentz: transport data.
- Nicola Morandini: machine learning.
- Jordi Martinez: cost calculation and delivery documentation.

The Streamlit interface owner is still to be confirmed.

## AI assistance and contributions

ChatGPT assisted with generating and explaining costs.py, example.py
and test_costs.py, preparing this README, and guiding testing and GitHub use.

Jordi ran the cost example and all nine tests locally, and uploaded
the cost files to the shared repository.

AI assistance is acknowledged in the generated Python files.
The shared project tracker contains the contribution matrix and AI log,
which the team updates as work progresses.