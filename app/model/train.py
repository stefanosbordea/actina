"""Independent provisional LightGBM reference; replace with Stefanos's reviewed model."""
import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TZ = "Asia/Nicosia"
WEATHER = ["shortwave_radiation", "cloud_cover", "temperature_2m",
           "relative_humidity_2m", "et0_fao_evapotranspiration", "precipitation"]
TEST_START, TEST_END = "2026-07-01", "2026-09-30"
VALIDATION_START = "2026-06-01"
FEATURES = ["hour_sin", "hour_cos", "year_sin", "year_cos", "month"] + [
    f"{col}_lag{lag}" for lag in (2, 3) for col in WEATHER] + [
    f"{col}_at_issue" for col in WEATHER] + [
    "issue_day_radiation_mean", "issue_day_radiation_max", "issue_day_cloud_mean"]


def load_weather(path):
    frame = pd.read_csv(path)
    required = {"time", *WEATHER}
    if not required <= set(frame):
        raise ValueError(f"Missing weather columns: {sorted(required - set(frame))}")
    # Offsets distinguish both copies of the autumn clock-change hour.
    if not frame["time"].astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
        raise ValueError("Weather timestamps require explicit timezone offsets")
    times = pd.to_datetime(frame.pop("time"), utc=True, errors="raise").dt.tz_convert(TZ)
    frame.index = pd.DatetimeIndex(times, name="time")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Weather timestamps must be unique and chronological")
    if len(frame) > 1 and not (np.diff(frame.index.as_unit("ns").asi8) == 3600 * 10**9).all():
        raise ValueError("Weather series must have contiguous UTC hours")
    frame = frame[WEATHER].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Weather contains missing or nonfinite values")
    if (frame.shortwave_radiation < 0).any():
        raise ValueError("Negative radiation")
    return frame


def build_features(weather):
    """All weather sources precede yesterday's 18:00 daily issue cutoff."""
    frame = pd.DataFrame(index=weather.index)
    dates = [t.date().isoformat() for t in weather.index]
    hours = weather.index.hour
    issues = pd.DatetimeIndex([pd.Timestamp((t.date() - timedelta(days=1)).isoformat() +
                                          "T18:00", tz=TZ) for t in weather.index])
    frame["forecast_issue_time"] = issues
    frame["hour_sin"] = np.sin(2 * np.pi * hours / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * hours / 24)
    frame["year_sin"] = np.sin(2 * np.pi * weather.index.dayofyear / 365.25)
    frame["year_cos"] = np.cos(2 * np.pi * weather.index.dayofyear / 365.25)
    frame["month"] = weather.index.month
    keyed = weather.copy()
    keyed["date"] = dates
    keyed["hour"] = hours
    keyed["source_time"] = weather.index
    # Repeated local DST hours average only already-known observations.
    by_hour = keyed.groupby(["date", "hour"])[WEATHER].mean()
    latest_hour = keyed.groupby(["date", "hour"])["source_time"].max()
    for lag in (2, 3):
        keys = pd.MultiIndex.from_tuples([((t.date() - timedelta(days=lag)).isoformat(), t.hour)
                                        for t in weather.index], names=["date", "hour"])
        values = by_hour.reindex(keys)
        for col in WEATHER:
            frame[f"{col}_lag{lag}"] = values[col].to_numpy()
        source_times = latest_hour.reindex(keys)
        frame[f"lag{lag}_source_time"] = pd.DatetimeIndex(source_times)
    issue_keys = pd.MultiIndex.from_tuples([(t.date().isoformat(), 18) for t in issues],
                                         names=["date", "hour"])
    for col in WEATHER:
        frame[f"{col}_at_issue"] = by_hour.reindex(issue_keys)[col].to_numpy()
    observed = keyed[keyed.hour.between(6, 18)]
    aggregates = observed.groupby("date").agg(
        issue_day_radiation_mean=("shortwave_radiation", "mean"),
        issue_day_radiation_max=("shortwave_radiation", "max"),
        issue_day_cloud_mean=("cloud_cover", "mean"))
    issue_dates = [t.date().isoformat() for t in issues]
    for col in aggregates:
        frame[col] = aggregates.reindex(issue_dates)[col].to_numpy()
    frame["latest_feature_time"] = issues
    frame["actual"] = weather.shortwave_radiation
    frame = frame.dropna(subset=FEATURES + ["lag2_source_time", "lag3_source_time"])
    assert_feature_cutoffs(frame)
    return frame


def assert_feature_cutoffs(frame):
    if any((frame[col] > frame.forecast_issue_time).any()
           for col in ["lag2_source_time", "lag3_source_time", "latest_feature_time"]):
        raise ValueError("Feature timestamp exceeds forecast issue time")
    if (frame.forecast_issue_time >= frame.index).any():
        raise ValueError("Forecast issue must precede its target")


def split_frames(frame, train_before=TEST_START):
    if train_before != TEST_START:
        raise ValueError("Frozen protocol requires all training targets before 2026-07-01")
    train = frame[frame.index.date < date.fromisoformat(TEST_START)]
    test = frame[(frame.index.date >= date.fromisoformat(TEST_START)) &
                 (frame.index.date <= date.fromisoformat(TEST_END))]
    if train.empty or test.empty or train.index.max() >= test.index.min():
        raise ValueError("Invalid chronological split")
    return train, test


def fit(frame):
    from lightgbm import LGBMRegressor
    # No search: a fixed default-size model with bounded desktop CPU use.
    model = LGBMRegressor(n_estimators=100, random_state=20260930, n_jobs=2, verbosity=-1)
    model.fit(frame[FEATURES], frame.actual)
    return model


def predict(model, frame):
    return np.maximum(0.0, model.predict(frame[FEATURES]))


def choose_threshold(actual, predicted):
    """June only: retain brief's 600 if precision>=0.9, recall>=0.7 and support>=50."""
    options = []
    for threshold in (400, 500, 600, 700):
        true = np.asarray(actual) >= threshold
        flags = np.asarray(predicted) >= threshold
        tp = int((true & flags).sum())
        precision = tp / int(flags.sum()) if flags.any() else 0.0
        recall = tp / int(true.sum()) if true.any() else 0.0
        fhalf = 1.25 * precision * recall / (.25 * precision + recall) if precision + recall else 0.0
        options.append({"threshold_w_m2": threshold, "precision": precision, "recall": recall,
                        "f0_5": fhalf, "predicted_positive": int(flags.sum()),
                        "actual_positive": int(true.sum())})
    feasible = [x for x in options if x["precision"] >= .9 and x["recall"] >= .7 and
                min(x["predicted_positive"], x["actual_positive"]) >= 50]
    chosen = min(feasible, key=lambda x: abs(x["threshold_w_m2"] - 600)) if feasible else max(
        options, key=lambda x: (x["f0_5"], -abs(x["threshold_w_m2"] - 600)))
    return chosen["threshold_w_m2"], options


def issue_time_persistence(weather, target_index):
    """Latest same local hour available at yesterday18:00, with explicit source time."""
    actual = weather.actual if "actual" in weather else weather.shortwave_radiation
    table = pd.DataFrame({"actual": actual, "source_time": weather.index,
                          "date": [t.date().isoformat() for t in weather.index],
                          "hour": weather.index.hour})
    keyed = table.groupby(["date", "hour"]).agg(actual=("actual", "mean"), source_time=("source_time", "max"))
    keys = pd.MultiIndex.from_tuples([((t.date() - timedelta(days=1 if t.hour <= 18 else 2)).isoformat(), t.hour)
                                    for t in target_index], names=["date", "hour"])
    matched = keyed.reindex(keys)
    return pd.DataFrame({"baseline": matched.actual.to_numpy(),
                         "baseline_source_time": pd.DatetimeIndex(matched.source_time)}, index=target_index)


def make_predictions(model, train, test):
    climate = train.groupby([train.index.month, train.index.hour]).actual.mean()
    keys = pd.MultiIndex.from_arrays([test.index.month, test.index.hour])
    persistence = issue_time_persistence(pd.concat([train, test]), test.index)
    if (persistence.baseline_source_time > test.forecast_issue_time).any():
        raise ValueError("Persistence source exceeds issue time")
    frame = pd.DataFrame({"time": [t.isoformat() for t in test.index], "actual": test.actual.to_numpy(),
                          "predicted": predict(model, test),
                          "baseline": persistence.baseline.to_numpy(),
                          "baseline_day2": test.shortwave_radiation_lag2.to_numpy(),
                          "baseline_source_time": [t.isoformat() for t in persistence.baseline_source_time],
                          "climatology": climate.reindex(keys).to_numpy(),
                          "forecast_issue_time": [t.isoformat() for t in test.forecast_issue_time]})
    if frame.climatology.isna().any():
        raise ValueError("Train-only month/hour climatology lacks required groups")
    return frame


def run(weather_path=ROOT / "data/paphos_weather.csv", output=ROOT):
    output = Path(output)
    for folder in ("model", "results", "data"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    weather = load_weather(weather_path)
    frame = build_features(weather)
    train, test = split_frames(frame)
    development = train[train.index.date < date.fromisoformat(VALIDATION_START)]
    validation = train[train.index.date >= date.fromisoformat(VALIDATION_START)]
    reference = fit(development)
    validation_predicted = predict(reference, validation)
    threshold, threshold_options = choose_threshold(validation.actual, validation_predicted)
    model = fit(train)
    model_path = output / "model/reference_lightgbm.txt"
    model.booster_.save_model(str(model_path))
    predictions = make_predictions(model, train, test)
    predictions.to_csv(output / "data/test_predictions.csv", index=False)
    day_forecast = pd.DataFrame({
        "time": predictions.time,
        "date": [t.date().isoformat() for t in test.index], "hour": test.index.hour,
        "predicted_radiation": predictions.predicted,
        "surplus_flag": predictions.predicted >= threshold,
        "forecast_issue_time": predictions.forecast_issue_time})
    day_forecast.to_csv(output / "data/day_forecast.csv", index=False)
    importance = pd.DataFrame({"feature": FEATURES,
                               "gain": model.booster_.feature_importance(importance_type="gain"),
                               "split_count": model.booster_.feature_importance(importance_type="split")})
    importance.sort_values("gain", ascending=False).to_csv(output / "results/feature_importance.csv", index=False)
    metadata = {
        "model_status": "Independent provisional reference; replaceable by Stefanos's reviewed model",
        "estimator": "LightGBM LGBMRegressor; 100 trees, other learning defaults; no hyperparameter search",
        "seed": 20260930, "feature_names": FEATURES, "features_count": len(FEATURES),
        "train_rows": len(train), "train_first_target": train.index.min().isoformat(),
        "train_last_target": train.index.max().isoformat(), "train_target_before": TEST_START,
        "validation_rows": len(validation), "validation_start": VALIDATION_START,
        "validation_model_last_target": development.index.max().isoformat(),
        "test_rows": len(test), "test_first_target": test.index.min().isoformat(),
        "test_last_target": test.index.max().isoformat(), "threshold_w_m2": threshold,
        "threshold_selection": "June validation only; closest to600 with precision>=0.90, recall>=0.70, >=50 positives; else highest F0.5",
        "threshold_validation": threshold_options,
        "forecast_issue": "18:00 Asia/Nicosia on the preceding local date",
        "persistence": "Latest same local hour: preceding day for targethours00–18; day-2 for19–23; source<=18:00issue",
        "persistence_day2": "Older same local hour two dates earlier, retained secondary control",
        "climatology": "Mean for target local hour and month from training targets only",
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256((output / "data/test_predictions.csv").read_bytes()).hexdigest(),
        "weather_sha256": hashlib.sha256(Path(weather_path).read_bytes()).hexdigest(),
        "leakage_audit": {
            "all_weather_source_times_at_or_before_issue": True,
            "training_targets_before_test": True, "test_tuning": False,
            "target_day_realized_weather_features": False,
            "latest_feature_time_minus_issue_seconds_max": float(
                (frame.latest_feature_time - frame.forecast_issue_time).dt.total_seconds().max()),
            "caveat": "Temporal cutoff audit only. IFS historical values are revised model reconstruction; original issue-time publication vintages were not available or tested."},
        "limitations": ["Retrospective gridded-weather experiment; not operational forecast validation.",
                        "Radiation threshold is a solar availability proxy, not observed grid surplus or curtailment.",
                        "No target-day NWP forecast input; no actual metered plant or grid data.",
                        "Water demand, electricity tariffs and emissions belong to separate illustrative scenarios."]}
    (output / "model/reference_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "results/leakage_audit.json").write_text(json.dumps(metadata["leakage_audit"], indent=2) + "\n")
    print(json.dumps({"train_rows": len(train), "test_rows": len(test), "threshold_w_m2": threshold,
                      "model_sha256": metadata["model_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weather", type=Path, default=ROOT / "data/paphos_weather.csv")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.weather, args.output)
