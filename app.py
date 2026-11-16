"""Demonstration of the fair-rent ranking slider.

AI assistance: generated with ChatGPT on 16 November 2026.
Uses fictional inputs; real-data integration is pending.
"""

import streamlit as st

from costs import calculate_monthly_cost, calculate_ranking_score


st.title("Where Should I Live?")
st.info("Demo using fictional apartment data.")

# Example apartment: all prices are CHF per month.
actual_rent = 1800.0
fair_rent = 2000.0

costs = calculate_monthly_cost(
    rent_monthly=actual_rent,
    pass_monthly=150.0,
    commute_minutes_one_way=30.0,
    office_days_monthly=20,
    hourly_time_value=37.50,
)

st.write(f"Actual rent: CHF {actual_rent:,.2f}")
st.write(f"Estimated fair rent: CHF {fair_rent:,.2f}")

# The chosen weight controls the fair-rent adjustment.
p = st.slider(
    "How much should fair rent influence the ranking?",
    min_value=0.0,
    max_value=1.0,
    value=0.0,
    step=0.1,
    help="0 = total cost only. 1 = full fair-rent adjustment.",
)

score = calculate_ranking_score(
    costs["total_cost_monthly"],
    actual_rent,
    fair_rent,
    p,
)

st.metric(
    "Monthly cash expenses",
    f"CHF {costs['cash_cost_monthly']:,.2f}",
)

st.metric(
    "Monthly cost including commuting time",
    f"CHF {costs['total_cost_monthly']:,.2f}",
)

st.metric("Ranking score — lower is better", f"{score:,.2f}")

st.caption(
    "Score = total monthly cost + p × (actual rent − fair rent). "
    "Changing the slider changes the ranking score, not your expenses."
)
