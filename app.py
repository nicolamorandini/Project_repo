"""Demo of transport costs and fair-rent ranking.

AI assistance: generated with ChatGPT on 16 November 2026.
Default values are fictional. Real-data integration is pending.
"""

import streamlit as st

from costs import calculate_monthly_cost, calculate_ranking_score
from transport_modes import calculate_transport_cost


st.title("Where Should I Live?")
st.info(
    "Demo: all starting values are fictional. "
    "Enter your own assumptions to explore the costs."
)

st.header("Apartment")

actual_rent = st.number_input(
    "Actual monthly rent including charges (CHF)",
    min_value=0.0,
    value=1800.0,
)

fair_rent = st.number_input(
    "Estimated fair monthly rent on the same basis (CHF)",
    min_value=0.0,
    value=2000.0,
)

st.caption(
    "For this demo, enter fair rent manually. "
    "The trained model will supply it in the finished app."
)

st.header("Commute")

mode = st.selectbox(
    "Transport mode",
    ["Public transport", "Bike", "Motorbike", "Car"],
)

office_days = st.number_input(
    "Office days per month",
    min_value=0,
    max_value=31,
    value=20,
)

commute_minutes = st.number_input(
    "One-way commuting time for the selected mode (minutes)",
    min_value=0.0,
    value=30.0,
    key=f"time_{mode}",
)

hourly_value = st.number_input(
    "Value assigned to one hour of your time (CHF)",
    min_value=0.0,
    value=37.50,
)

st.caption(
    "Enter travel time for the selected mode. "
    "Automatic route times are not connected yet."
)

if mode == "Public transport":
    transport_monthly = st.number_input(
        "Monthly pass cost, or annual pass price divided by 12 (CHF)",
        min_value=0.0,
        value=150.0,
    )

else:
    distance = st.number_input(
        "One-way commuting distance for this mode (km)",
        min_value=0.0,
        value=10.0,
        key=f"distance_{mode}",
    )

    # Fictional defaults: energy/km, maintenance/km,
    # annual ownership and monthly parking.
    defaults = {
        "Bike": (0.00, 0.05, 120.0, 0.0),
        "Motorbike": (0.06, 0.04, 1200.0, 20.0),
        "Car": (0.12, 0.08, 3600.0, 100.0),
    }
    energy, maintenance, ownership, parking = defaults[mode]

    energy_rate = st.number_input(
        "Fuel or electricity cost per km (CHF)",
        min_value=0.0,
        value=energy,
        step=0.01,
        key=f"energy_{mode}",
    )

    maintenance_rate = st.number_input(
        "Maintenance cost per km (CHF)",
        min_value=0.0,
        value=maintenance,
        step=0.01,
        key=f"maintenance_{mode}",
    )

    annual_ownership = st.number_input(
        "Annual ownership cost (CHF)",
        min_value=0.0,
        value=ownership,
        key=f"ownership_{mode}",
        help=(
            "Include insurance, vehicle taxes and annual loss of value. "
            "Exclude fuel, maintenance and parking entered separately."
        ),
    )

    parking_cost = st.number_input(
        "Monthly parking cost (CHF)",
        min_value=0.0,
        value=parking,
        key=f"parking_{mode}",
    )

    transport = calculate_transport_cost(
        mode=mode.lower(),
        distance_km_one_way=distance,
        office_days_monthly=office_days,
        energy_cost_per_km=energy_rate,
        maintenance_cost_per_km=maintenance_rate,
        annual_ownership_cost=annual_ownership,
        parking_monthly=parking_cost,
    )

    transport_monthly = transport["transport_cost_monthly"]

    st.caption(
        "This comparison includes the full ownership cost, including "
        "depreciation. Depreciation is loss of value, not a monthly bill. "
        "Ownership and monthly parking costs remain even with no commuting."
    )

# Reuse the existing function. Its pass_monthly parameter
# receives the selected mode's monthly transport cost.
costs = calculate_monthly_cost(
    rent_monthly=actual_rent,
    pass_monthly=transport_monthly,
    commute_minutes_one_way=commute_minutes,
    office_days_monthly=office_days,
    hourly_time_value=hourly_value,
)

st.header("Ranking preference")

p = st.slider(
    "Weight given to the fair-rent difference",
    min_value=0.0,
    max_value=1.0,
    value=0.0,
    step=0.1,
)

score = calculate_ranking_score(
    costs["total_cost_monthly"],
    actual_rent,
    fair_rent,
    p,
)

st.header("Monthly comparison")

st.metric("Transport cost", f"CHF {transport_monthly:,.2f}")

# Use a broad cost label because vehicle costs can include depreciation.
st.metric(
    "Rent + transport, including any depreciation",
    f"CHF {costs['cash_cost_monthly']:,.2f}",
)

st.metric(
    "Value of commuting time",
    f"CHF {costs['time_cost_monthly']:,.2f}",
)

st.metric(
    "Total cost including commuting time",
    f"CHF {costs['total_cost_monthly']:,.2f}",
)

st.metric("Ranking score — lower is better", f"{score:,.2f}")

st.caption(
    "Score = total cost + p × (actual rent − fair rent). "
    "The ranking adjustment does not change your expenses."
)