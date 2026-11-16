"""Monthly commuting costs for bike, motorbike and car.

AI assistance: generated with ChatGPT on 16 November 2026.
Example values are fictional, not researched Swiss prices.
"""

import math


def calculate_transport_cost(
    mode,
    distance_km_one_way,
    office_days_monthly,
    energy_cost_per_km=0.0,
    maintenance_cost_per_km=0.0,
    annual_ownership_cost=0.0,
    parking_monthly=0.0,
):
    """Calculate monthly transport expenses in CHF.

    annual_ownership_cost includes insurance, vehicle taxes,
    and depreciation (purchase price minus expected resale value,
    divided by years of ownership).

    Maintenance must be included only in maintenance_cost_per_km,
    to avoid counting the same expense twice.

    This model assigns the full ownership cost to the vehicle.
    Commuting time is calculated separately.
    """
    if mode not in ("bike", "motorbike", "car"):
        raise ValueError("Mode must be bike, motorbike or car.")

    inputs = {
        "distance_km_one_way": distance_km_one_way,
        "office_days_monthly": office_days_monthly,
        "energy_cost_per_km": energy_cost_per_km,
        "maintenance_cost_per_km": maintenance_cost_per_km,
        "annual_ownership_cost": annual_ownership_cost,
        "parking_monthly": parking_monthly,
    }

    for name, value in inputs.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{name} must be a finite, non-negative number.")

    if office_days_monthly > 31:
        raise ValueError("Office days cannot exceed 31 per month.")

    # Two journeys per office day: home to work and back.
    monthly_km = 2 * distance_km_one_way * office_days_monthly

    energy_monthly = monthly_km * energy_cost_per_km
    maintenance_monthly = monthly_km * maintenance_cost_per_km
    ownership_monthly = annual_ownership_cost / 12

    transport_monthly = (
        energy_monthly
        + maintenance_monthly
        + ownership_monthly
        + parking_monthly
    )

    return {
        "mode": mode,
        "monthly_km": monthly_km,
        "energy_monthly": energy_monthly,
        "maintenance_monthly": maintenance_monthly,
        "ownership_monthly": ownership_monthly,
        "parking_monthly": parking_monthly,
        "transport_cost_monthly": transport_monthly,
    }


if __name__ == "__main__":
    # Fictional examples solely to check the calculation.
    examples = [
        ("bike", 0.00, 0.05, 120.0, 0.0),
        ("motorbike", 0.06, 0.04, 1200.0, 20.0),
        ("car", 0.12, 0.08, 3600.0, 100.0),
    ]

    for mode, energy, maintenance, ownership, parking in examples:
        result = calculate_transport_cost(
            mode=mode,
            distance_km_one_way=10.0,
            office_days_monthly=20,
            energy_cost_per_km=energy,
            maintenance_cost_per_km=maintenance,
            annual_ownership_cost=ownership,
            parking_monthly=parking,
        )
        cost = result["transport_cost_monthly"]
        print(f"{mode}: CHF {cost:.2f}/month")