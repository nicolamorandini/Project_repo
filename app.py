"""Real Flatfox listings, saved ML benchmark and transport costs.

AI assistance: ChatGPT, 2026-11-28. Integration for team review.
"""
import pandas as pd
import streamlit as st
from real_data import load_listings, predict_rents, load_transport
from costs import calculate_monthly_cost, calculate_ranking_score, salary_to_hourly_value
from transport_modes import calculate_transport_cost

st.set_page_config(page_title='Where Should I Live?', layout='wide')
st.title('Where Should I Live?')
st.caption('Real Flatfox listing snapshot • workplace: Zürich HB • CHF/month')

@st.cache_data
def listing_data():
    """Load the repository snapshot and compute gross monthly rent predictions."""
    return predict_rents(load_listings())

try:
    listings, metadata = listing_data()
except Exception as error:
    st.error(f'Cannot load the real listings/model: {error}')
    st.info('Use Python 3.12 and install requirements.txt. No fictional fallback is used.')
    st.stop()

st.sidebar.header('Your preferences')
salary = st.sidebar.number_input('Annual salary including 13th salary (CHF)', min_value=0.0, value=0.0)
weekly_hours = st.sidebar.number_input('Weekly working hours', min_value=1.0, value=40.0)
fraction = st.sidebar.slider('Fraction of hourly pay assigned to travel time', 0.0, 1.0, 1.0, 0.1)
days = st.sidebar.number_input('Office days per month', min_value=0, max_value=31, value=20)
hourly = salary_to_hourly_value(salary, weekly_hours, fraction)
st.sidebar.caption(f'Time value: CHF {hourly:.2f}/hour. Enter your salary to include time costs.')
budget = st.sidebar.number_input('Maximum gross monthly rent (CHF)', min_value=0.0, value=float(listings.rent_gross.max()))
rooms = st.sidebar.number_input('Minimum rooms', min_value=0.0, value=0.0, step=0.5)
municipalities = st.sidebar.multiselect('Municipalities (empty = all)', sorted(listings.municipality.unique()))
p = st.sidebar.slider('Fair-rent ranking weight p', 0.0, 1.0, 0.0, 0.1)
mode = st.sidebar.selectbox('Transport mode', ['Public transport', 'Bike', 'Motorbike', 'Car'])
fare_class = st.sidebar.selectbox('Public transport class', [2, 1])
annual = st.sidebar.checkbox('Use annual pass price divided by 12')
filtered = listings[(listings.rent_gross <= budget) & (listings.rooms >= rooms)].copy()
if municipalities:
    filtered = filtered[filtered.municipality.isin(municipalities)]
if filtered.empty:
    st.info('No listings match these filters.')
    st.stop()

st.caption(f'{len(filtered)} matching listings. Asking rents are snapshots; check availability on Flatfox.')
st.info(f'Fair rent is a model estimate. Held-out mean absolute error: CHF {metadata["mae"]:.0f}/month. '
        'Some displayed listings were used to train the model, so their estimates are not independent valuations.')
try:
    transport = load_transport(fare_class=fare_class, annual=annual)
except Exception as error:
    st.error(f'Transport data cannot be read: {error}')
    st.stop()
joined = filtered.merge(transport, on='municipality', how='left', validate='many_to_one')

if mode == 'Public transport':
    st.caption('Travel times: municipality station → Zürich HB, not door to door. '
               'Pass prices and route-zone counts come from the team CSVs; expired tariffs are excluded.')
    ready = joined.pt_minutes.notna() & joined.transport_monthly.notna()
    ranked = joined.loc[ready].copy()
    results = []
    for row in ranked.itertuples():
        cost = calculate_monthly_cost(float(row.rent_gross), float(row.transport_monthly), float(row.pt_minutes), int(days), hourly)
        cost['score'] = calculate_ranking_score(cost['total_cost_monthly'], float(row.rent_gross), float(row.fair_rent), p)
        results.append(cost)
    if results:
        for column in results[0]:
            ranked[column] = [item[column] for item in results]
        ranked = ranked.sort_values(['score', 'id'])
        st.subheader('Ranked apartments — lowest score first')
        st.dataframe(ranked[['id', 'municipality', 'rooms', 'surface_m2', 'rent_gross', 'fair_rent', 'verdict',
                            'pt_minutes', 'transport_monthly', 'cash_cost_monthly', 'time_cost_monthly',
                            'total_cost_monthly', 'score', 'travel_date', 'url']].reset_index(drop=True))
    st.caption(f'{len(ranked)} apartments can be ranked; {len(joined) - len(ranked)} have missing route or valid tariff data.')
    if not ready.all():
        with st.expander('Listings excluded from public transport ranking'):
            st.dataframe(joined.loc[~ready, ['id', 'municipality', 'rent_gross', 'fair_rent', 'url']])
        st.info('To collect route times, run the transport refresh commands in README.md. '
                'Municipalities outside the team route CSV remain unranked.')
else:
    st.subheader('Choose an apartment for your vehicle cost calculation')
    st.dataframe(filtered[['id', 'municipality', 'rooms', 'surface_m2', 'rent_gross', 'fair_rent', 'verdict', 'url']])

st.subheader('Apartment details and cost breakdown')
detail_order = list(ranked.id) + list(filtered.loc[~filtered.id.isin(ranked.id), 'id']) if mode == 'Public transport' else list(filtered.id)
options = filtered.set_index('id').loc[detail_order]
listing_id = st.selectbox('Apartment', list(options.index), format_func=lambda i: f'{i} — {options.loc[i, "municipality"]} — CHF {options.loc[i, "rent_gross"]:,.0f}')
flat = joined[joined.id == listing_id].iloc[0]
st.write(f'Gross rent: **CHF {flat.rent_gross:,.0f}** · Model fair rent: **CHF {flat.fair_rent:,.0f}** · {flat.verdict}')
st.link_button('View listing on Flatfox', flat.url)
if flat.model_training_listing:
    st.caption('This listing was in the model training set.')

if mode == 'Public transport':
    if pd.isna(flat.pt_minutes) or pd.isna(flat.transport_monthly):
        st.warning('A complete cost cannot be calculated for this apartment: its route time or valid tariff is missing.')
        st.stop()
    minutes = float(flat.pt_minutes)
    monthly = float(flat.transport_monthly)
    st.write(f'{flat.station} → Zürich HB: {minutes:g} minutes one way. Timetable date: {flat.travel_date}.')
else:
    # Do not invent vehicle prices or infer motorbike travel time from a car route.
    prefix = 'bike' if mode == 'Bike' else 'car' if mode == 'Car' else None
    km = flat.get(f'{prefix}_km') if prefix else None
    time = flat.get(f'{prefix}_minutes') if prefix else None
    key = f'{listing_id}_{mode}'
    st.caption('Enter your own vehicle costs. Missing route data must be supplied explicitly; no fictional defaults are used. '
               'Stored routes, where available, are from the municipality station, not the apartment.')
    distance = st.number_input('One-way route distance (km)', min_value=0.0, value=float(km) if pd.notna(km) else None, key=key+'km')
    minutes = st.number_input('One-way route time (minutes)', min_value=0.0, value=float(time) if pd.notna(time) else None, key=key+'time')
    energy = st.number_input('Energy/fuel cost per km (CHF; enter 0 for a regular bike)', min_value=0.0, value=None, key=mode+'energy')
    maintenance = st.number_input('Maintenance per km (CHF)', min_value=0.0, value=None, key=mode+'maintenance')
    ownership = st.number_input('Annual insurance, vehicle taxes and depreciation (CHF)', min_value=0.0, value=None, key=mode+'ownership')
    parking = st.number_input('Monthly parking cost (CHF)', min_value=0.0, value=None, key=mode+'parking')
    if any(value is None for value in [distance, minutes, energy, maintenance, ownership, parking]):
        st.info('Complete all vehicle inputs, using 0 where a cost does not apply.')
        st.stop()
    vehicle = calculate_transport_cost(mode.lower(), distance, int(days), energy, maintenance, ownership, parking)
    monthly = vehicle['transport_cost_monthly']
    st.caption('Full vehicle ownership cost is included, even with zero commuting days. Depreciation is loss of value, not a monthly bill. '
               'Do not include energy, maintenance or parking twice.')

cost = calculate_monthly_cost(float(flat.rent_gross), monthly, minutes, int(days), hourly)
score = calculate_ranking_score(cost['total_cost_monthly'], float(flat.rent_gross), float(flat.fair_rent), p)
a, b, c = st.columns(3)
a.metric('Transport / month', f'CHF {monthly:,.2f}')
b.metric('Rent + transport', f'CHF {cost["cash_cost_monthly"]:,.2f}')
c.metric('Commuting time value', f'CHF {cost["time_cost_monthly"]:,.2f}')
st.metric('Total including time', f'CHF {cost["total_cost_monthly"]:,.2f}')
st.metric('Ranking score', f'{score:,.2f}')
st.caption('Score = total cost + p × (actual gross rent − predicted gross rent). Lower is better; the score is not an expense. '
           'Vehicle totals can include depreciation.')
