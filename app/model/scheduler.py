"""Illustrative water-storage scheduling; SciPy linprog uses the upstream HiGHS solver.

Actual radiation and temperature are evaluation/display inputs, never decision inputs.
Radiation above a threshold is a weather proxy, not measured electricity curtailment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog

KWH_PER_M3 = 3.4
SCENARIO_GRID_KG_PER_KWH = 0.65


def _hours(values, name):
    try:
        values = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain 24 numeric hourly values") from exc
    if values.shape != (24,) or not np.isfinite(values).all():
        raise ValueError(f"{name} must contain 24 finite hourly values")
    return values


def schedule_day(predicted, actual, temperature, tank_capacity=4000.0,
                 unit_capacity=500.0, threshold=600.0, demand_scale=1.0,
                 season="summer", forecast_temperature_c=28.0,
                 renewable_displacement_share=0.0):
    """Return frame, totals, assumptions, status for one 24-hour illustrative day.

    Demand is a declared day-ahead scenario: base 100 m³/h, summer +20 m³/h,
    and +2 m³/h per forecast degree above 30°C. Realized weather is not used.
    Inputs must be 24 ordered local standard hourly bins; DST days need explicit
    normalization upstream. Storage starts/ends 50% full, minimum 20%. Production
    and consumption are uniform within each hour, so endpoint bounds also bound
    within-hour storage. No ramp, minimum-run, salinity or maintenance model.
    """
    parameters = dict(tank_capacity=tank_capacity, unit_capacity=unit_capacity,
                      threshold=threshold, demand_scale=demand_scale,
                      forecast_temperature_c=forecast_temperature_c,
                      renewable_displacement_share=renewable_displacement_share)
    for name, value in parameters.items():
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
            raise ValueError(f"{name} must be finite and numeric")
    if tank_capacity < 0 or unit_capacity <= 0 or threshold < 0 or demand_scale <= 0:
        raise ValueError("tank and threshold must be nonnegative; capacity and demand scale positive")
    if not 0 <= renewable_displacement_share <= 1:
        raise ValueError("renewable_displacement_share must be between 0 and 1")
    if season not in ("summer", "winter", "shoulder"):
        raise ValueError("season must be summer, winter or shoulder")
    if not -80 <= forecast_temperature_c <= 70:
        raise ValueError("forecast_temperature_c is outside the supported scenario range")
    actual = _hours(actual, "actual")
    temperature = _hours(temperature, "temperature")
    if (actual < 0).any() or ((temperature < -80) | (temperature > 70)).any():
        raise ValueError("radiation cannot be negative; temperature must be between -80 and 70°C")
    unavailable = predicted is None
    if unavailable:
        predicted = np.full(24, np.nan)
    else:
        try:
            predicted = np.asarray(predicted, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("predicted must contain 24 numeric hourly values") from exc
        if predicted.shape != (24,):
            raise ValueError("predicted must contain 24 hourly values")
        if (predicted[np.isfinite(predicted)] < 0).any() or np.isinf(predicted).any():
            raise ValueError("predicted radiation must be nonnegative or missing")
        unavailable = bool(np.isnan(predicted).any())
    demand = (100.0 + (20.0 if season == "summer" else 0.0)
              + 2.0 * max(0.0, forecast_temperature_c - 30.0)) * demand_scale
    if demand > unit_capacity + 1e-8:
        raise ValueError(f"infeasible: demand {demand:g} m³/h exceeds unit capacity {unit_capacity:g}; equal terminal storage forbids borrowing water")
    hour = np.arange(24)
    # Illustrative tariff scenario, independent of future realized radiation.
    price = np.where((hour >= 10) & (hour < 17), 101.0,
                     np.where((hour >= 17) & (hour < 23), 183.0, 130.0))
    initial = 0.5 * tank_capacity
    minimum = 0.2 * tank_capacity
    baseline = np.full(24, demand)
    if unavailable:
        production = baseline.copy()
        status = "fallback: unavailable forecast; flat baseline retained"
    else:
        # Forecast is only a small, deterministic preference within tariff ties.
        objective = np.r_[KWH_PER_M3 * price / 1000.0
                          - 1e-6 * predicted / max(1.0, float(predicted.max())), np.zeros(24)]
        equalities = np.zeros((24, 48))
        for h in hour:
            equalities[h, h] = -1.0
            equalities[h, 24 + h] = 1.0
            if h:
                equalities[h, 23 + h] = -1.0
        rhs = np.full(24, -demand)
        rhs[0] += initial
        bounds = [(0.0, float(unit_capacity))] * 24 + [(minimum, float(tank_capacity))] * 23 + [(initial, initial)]
        solved = linprog(objective, A_eq=equalities, b_eq=rhs, bounds=bounds, method="highs")
        if not solved.success:
            raise ValueError(f"infeasible or solver failed: {solved.message}")
        production = solved.x[:24]
        status = "optimized illustrative tariff schedule"
    storage = initial + np.cumsum(production - demand)
    storage_start = np.r_[initial, storage[:-1]]
    tolerance = 1e-6
    violations = int(np.count_nonzero((storage < minimum - tolerance) | (storage > tank_capacity + tolerance)))
    if (violations or abs(storage[-1] - initial) > tolerance
            or (production < -tolerance).any() or (production > unit_capacity + tolerance).any()):
        raise RuntimeError("schedule failed independent water/capacity/storage audit")
    predicted_proxy = (predicted >= threshold) & np.isfinite(predicted)
    actual_proxy = actual >= threshold
    energy = production * KWH_PER_M3
    baseline_energy = baseline * KWH_PER_M3
    energy_total = float(energy.sum())
    baseline_energy_total = float(baseline_energy.sum())
    if abs(baseline_energy_total - energy_total) > tolerance * KWH_PER_M3:
        raise RuntimeError("schedule failed matched-energy audit")
    cost = float(np.dot(energy, price) / 1000.0)
    baseline_cost = float(np.dot(baseline_energy, price) / 1000.0)
    actual_share = float(100 * energy[actual_proxy].sum() / energy_total)
    baseline_share = float(100 * baseline_energy[actual_proxy].sum() / baseline_energy_total)
    conditional = max(0.0, (actual_share - baseline_share) / 100.0) * energy_total * SCENARIO_GRID_KG_PER_KWH * renewable_displacement_share
    frame = pd.DataFrame(dict(hour=hour, predicted_radiation_w_m2=predicted,
                              actual_radiation_w_m2=actual, temperature_c=temperature,
                              demand_m3=baseline, baseline_m3=baseline, scheduled_m3=production,
                              baseline_storage_m3=np.full(24, initial), storage_start_m3=storage_start,
                              storage_m3=storage, price_eur_mwh=price, energy_kwh=energy,
                              baseline_energy_kwh=baseline_energy,
                              proxy_surplus_predicted=predicted_proxy, proxy_surplus_actual=actual_proxy,
                              normal_power_kw=baseline_energy, aquashift_power_kw=energy,
                              tank_level_m3=storage, surplus_flag=predicted_proxy))
    totals = dict(water_produced_m3=float(production.sum()), water_demand_m3=float(baseline.sum()),
                  unmet_demand_m3=0.0, energy_kwh=energy_total, baseline_energy_kwh=baseline_energy_total,
                  energy_saving_kwh=0.0,
                  cost_eur=cost, baseline_cost_eur=baseline_cost, cost_saving_eur=baseline_cost-cost,
                  cost_saving_percent=100 * (baseline_cost-cost) / baseline_cost,
                  scheduled_solar_proxy_share_pct=actual_share, baseline_solar_proxy_share_pct=baseline_share,
                  predicted_solar_proxy_share_pct=float(100 * energy[predicted_proxy].sum() / energy_total),
                  forecast_surplus_precision_pct=(float(100 * np.count_nonzero(predicted_proxy & actual_proxy) / predicted_proxy.sum()) if predicted_proxy.any() else None),
                  false_positive_forecast_hours=int(np.count_nonzero(predicted_proxy & ~actual_proxy)),
                  predicted_surplus_hours=int(predicted_proxy.sum()), actual_surplus_hours=int(actual_proxy.sum()),
                  safety_violations=violations, safety_minimum_m3=minimum, tank_capacity_m3=float(tank_capacity),
                  unit_capacity_m3_hour=float(unit_capacity), demand_m3_hour=float(demand),
                  initial_storage_m3=initial, final_storage_m3=float(storage[-1]),
                  min_storage_m3=float(storage.min()), max_storage_m3=float(storage.max()),
                  baseline_co2_kg=baseline_energy_total * SCENARIO_GRID_KG_PER_KWH,
                  schedule_co2_kg=energy_total * SCENARIO_GRID_KG_PER_KWH,
                  co2_saving_kg=0.0,
                  conditional_co2_saving_kg=conditional)
    assumptions = [
        "Illustrative one-unit scale, not a representation of an operating Paphos plant.",
        f"Demand assumption: 100 m³/h + {'20' if season == 'summer' else '0'} seasonal uplift + 2 per forecast degree above 30°C, scaled {demand_scale:g}; forecast temperature {forecast_temperature_c:g}°C.",
        "Actual target-day radiation and temperature do not enter the optimization or water demand.",
        "Clock tariff scenario: €101/MWh 10–16, €183/MWh 17–22, €130/MWh otherwise; not a billed tariff or forecast.",
        "3.4 kWh/m³ fixed specific energy; equal total water and equal initial/final storage for both schedules.",
        "Storage minimum 20%, start/end 50%; evenly distributed hourly flows. No ramp/minimum-run/maintenance model.",
        "Radiation threshold marks high-radiation weather only; grid surplus and curtailment are not observed.",
        "At constant 0.65 kg CO₂/kWh scenario intensity, equal energy gives zero carbon saving.",
        f"Conditional avoided emissions use displacement share {renewable_displacement_share:g}; valid only if additional renewable power actually displaces grid power and would otherwise spill. This is a scenario, not measured carbon.",
        "SciPy linprog with HiGHS performs linear optimization; it is adopted upstream software, not an invented AI scheduler.",
    ]
    if unavailable:
        assumptions.append("Missing forecast triggers the matched flat baseline; no schedule optimization is claimed.")
    if not predicted_proxy.any() and not unavailable:
        assumptions.append("No forecast high-radiation hours: any cost benefit is a tariff shift only.")
    return dict(frame=frame, totals=totals, assumptions=assumptions, status=status)
