"""Sites illustration: retrospective ET0 water budgeting and synthetic meter anomalies."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def sites_day(eto_mm, precipitation_mm=0.0, area_m2=5000.0,
              crop_coefficient=0.7, irrigation_efficiency=0.85,
              timer_depth_mm=6.0, soil_available_mm=0.0,
              inject_leak=True, seed=2026):
    """ET0, crop/soil settings and meter data are explicit demonstration inputs.

    1 mm over 1 m² = 1 litre. ET0 is retrospective weather, not an evaluated
    soil-moisture or irrigation forecast. IsolationForest trains on 28 simulated
    normal days; the query and optional injected leak are held out from fitting.
    """
    values = dict(eto_mm=eto_mm, precipitation_mm=precipitation_mm,
                  area_m2=area_m2, crop_coefficient=crop_coefficient,
                  irrigation_efficiency=irrigation_efficiency,
                  timer_depth_mm=timer_depth_mm, soil_available_mm=soil_available_mm)
    for name, value in values.items():
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
            raise ValueError(f"{name} must be finite and numeric")
    if (eto_mm < 0 or precipitation_mm < 0 or area_m2 <= 0
            or not 0 < crop_coefficient <= 1.5
            or not 0 < irrigation_efficiency <= 1
            or timer_depth_mm < 0 or soil_available_mm < 0):
        raise ValueError("ET0, rainfall, timer depth and soil reserve must be nonnegative; area, crop coefficient and efficiency positive")
    if not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
        raise ValueError("seed must be an integer between 0 and 2**32-1")
    effective_rain = 0.8 * precipitation_mm
    net_need = max(0.0, crop_coefficient * eto_mm - effective_rain - soil_available_mm)
    recommended = net_need / irrigation_efficiency * area_m2 / 1000.0
    timer = timer_depth_mm * area_m2 / 1000.0
    irrigation = dict(eto_mm=float(eto_mm), effective_rain_mm=float(effective_rain),
                      soil_available_mm=float(soil_available_mm), net_need_mm=float(net_need),
                      recommended_m3=float(recommended), timer_m3=float(timer),
                      water_difference_m3=float(timer-recommended),
                      water_difference_pct=(100*(timer-recommended)/timer if timer else None))
    rng = np.random.default_rng(seed)
    hour = np.arange(24)
    profile = np.where((hour >= 7) & (hour < 22), 0.06, 0.02)
    profile[6] += recommended
    history = np.maximum(0.0, profile + rng.normal(0, 0.004, size=(28, 24)))
    normal_query = np.maximum(0.0, profile + rng.normal(0, 0.004, size=24))
    center = np.median(history, axis=0)
    spread = np.maximum(history.std(axis=0), 0.002)
    train = ((history-center)/spread).reshape(-1, 1)
    # Labels for the injected event never enter model fitting or threshold choice.
    model = IsolationForest(n_estimators=100, contamination=0.02, random_state=seed)
    model.fit(train)
    night = (hour < 5) | (hour == 23)
    control_alert = (model.predict(((normal_query-center)/spread).reshape(-1, 1)) == -1) & night
    leak = np.zeros(24)
    if inject_leak:
        leak[1:5] = 0.3
    observed = normal_query + leak
    alert = (model.predict(((observed-center)/spread).reshape(-1, 1)) == -1) & night
    meter_frame = pd.DataFrame(dict(hour=hour, flow_m3_hour=observed,
                                    normal_flow_m3_hour=normal_query, alert=alert,
                                    injected_leak=leak > 0))
    detector = dict(alerts=int(alert.sum()), no_leak_false_alarms=int(control_alert.sum()),
                    injected_leak_hours=int(np.count_nonzero(leak)),
                    detected_injected_hours=int(np.count_nonzero(alert & (leak > 0))),
                    synthetic_leak_volume_m3=float(leak.sum()), training_days=28,
                    scope="synthetic meter fixture")
    assumptions = [
        "Retrospective ET0 weather illustration; no evaluated demand/soil forecast or operational irrigation controller.",
        "Crop coefficient, 80% effective rainfall, irrigation efficiency, soil reserve and fixed 6 mm timer are scenario inputs.",
        "The soil reserve is assumed plant-available water in millimetres, not a measured soil sensor.",
        "Water difference is against the chosen fixed timer; hot or dry scenarios can require MORE water.",
        "All meter readings are synthetic; the four-hour 0.3 m³/h leak is an injected demonstration fixture.",
        "IsolationForest is adopted scikit-learn software, trained only on 28 synthetic normal history days; the query and injected labels are held out.",
        "Night alerts use hours 00–04 and 23. This demonstration does not establish field accuracy, detection lead time or real water savings.",
    ]
    return dict(irrigation=irrigation, meter_frame=meter_frame, detector=detector, assumptions=assumptions)
