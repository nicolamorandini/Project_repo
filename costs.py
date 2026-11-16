"""Monthly housing/commuting costs and a separate fair-rent ranking score.

AI assistance: ChatGPT generated this initial draft and tests on 2026-11-16
from the project tracker and tutor email supplied by Jordi Martinez.
Human review and integration are pending; see AI_LOG.csv.
"""

from math import isfinite


def _nonnegative(name, value):
    """Reject missing, non-numeric, negative and non-finite inputs."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")


def calculate_monthly_cost(
    rent_monthly,
    pass_monthly,
    commute_minutes_one_way,
    office_days_monthly,
    hourly_time_value,
):
    """Return CHF/month costs and monthly commuting hours.

    rent_monthly: actual rent INCLUDING mandatory ancillary charges.
    pass_monthly: monthly pass price, or annual pass price divided by 12.
    commute_minutes_one_way: one-way journey time, not a round trip.
    office_days_monthly: commuting days; allow a monthly average.
    hourly_time_value: CHF/hour assigned to time, not a cash expense.

    All inputs must be provided explicitly; missing data is not zero.
    The calculation assumes two equal-length journeys per office day.
    Use the same journey scope for every listing (e.g. station to HB).
    Return unrounded values; round only when displaying results.
    """
    inputs = {
        "rent_monthly": rent_monthly,
        "pass_monthly": pass_monthly,
        "commute_minutes_one_way": commute_minutes_one_way,
        "office_days_monthly": office_days_monthly,
        "hourly_time_value": hourly_time_value,
    }
    for name, value in inputs.items():
        _nonnegative(name, value)
    if office_days_monthly > 31:
        raise ValueError("office_days_monthly cannot exceed 31")

    commute_hours = 2 * commute_minutes_one_way * office_days_monthly / 60
    time_cost = commute_hours * hourly_time_value
    cash_cost = rent_monthly + pass_monthly
    return {
        "rent_monthly": rent_monthly,
        "transport_cost_monthly": pass_monthly,
        "commute_hours_monthly": commute_hours,
        "time_cost_monthly": time_cost,
        "cash_cost_monthly": cash_cost,
        "total_cost_monthly": cash_cost + time_cost,
    }


def salary_to_hourly_value(annual_salary, weekly_work_hours, time_value_fraction=1.0):
    """Estimate CHF/hour as annual salary / (52 * weekly hours) * fraction.

    This is a simple modelling convention, not a statutory hourly wage.
    Annual salary includes any 13th salary. Specify gross/net consistently
    in the UI. A fraction of 1 values time at the full estimated hourly pay;
    0 ignores commuting time. This preference differs from ranking weight p.
    """
    for name, value in {
        "annual_salary": annual_salary,
        "weekly_work_hours": weekly_work_hours,
        "time_value_fraction": time_value_fraction,
    }.items():
        _nonnegative(name, value)
    if weekly_work_hours == 0:
        raise ValueError("weekly_work_hours must be greater than zero")
    if time_value_fraction > 1:
        raise ValueError("time_value_fraction must be between 0 and 1")
    return annual_salary / (52 * weekly_work_hours) * time_value_fraction


def calculate_ranking_score(total_cost_monthly, actual_rent_monthly,
                            fair_rent_monthly, p=0.0):
    """Task 21: total cost + p * (actual rent - predicted fair rent).

    Lower scores rank first. p must be non-negative; the team chooses the
    slider range. This is a preference score, NOT an amount the user pays.
    Actual and fair rents must use the same charges basis and CHF/month.
    When p=0, a fair-rent estimate is not needed and may be None.
    """
    for name, value in {
        "total_cost_monthly": total_cost_monthly,
        "actual_rent_monthly": actual_rent_monthly,
        "p": p,
    }.items():
        _nonnegative(name, value)
    if p == 0:
        return total_cost_monthly
    _nonnegative("fair_rent_monthly", fair_rent_monthly)
    return total_cost_monthly + p * (actual_rent_monthly - fair_rent_monthly)
