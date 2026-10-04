"""Evaluate a complete held-out prediction CSV against canonical weather and safe baselines."""
import argparse
import hashlib
import io
import json
import platform
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.train import TEST_START, TEST_END, TZ, build_features, issue_time_persistence, load_weather, split_frames


def expected_predictions(weather):
    train, test = split_frames(build_features(weather))
    climate = train.groupby([train.index.month, train.index.hour]).actual.mean()
    keys = pd.MultiIndex.from_arrays([test.index.month, test.index.hour])
    persistence = issue_time_persistence(weather, test.index)
    if (persistence.baseline_source_time > test.forecast_issue_time).any():
        raise ValueError("Persistence source exceeds issue time")
    return pd.DataFrame({"actual": test.actual, "baseline": persistence.baseline,
                         "baseline_day2": test.shortwave_radiation_lag2,
                         "baseline_source_time": persistence.baseline_source_time,
                         "climatology": climate.reindex(keys).to_numpy(),
                         "forecast_issue_time": test.forecast_issue_time}, index=test.index)


def validate_predictions(frame, expected, join_canonical=False):
    frame = frame.copy()
    required = {"time", "predicted"} if join_canonical else {"time", "actual", "predicted", "baseline"}
    if not required <= set(frame):
        raise ValueError(f"Missing prediction columns: {sorted(required - set(frame))}")
    if not frame.time.astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
        raise ValueError("Prediction timestamps require explicit timezone offsets")
    times = pd.to_datetime(frame.pop("time"), utc=True, errors="raise").dt.tz_convert(TZ)
    frame.index = pd.DatetimeIndex(times, name="time")
    if frame.index.has_duplicates:
        raise ValueError("Duplicate prediction timestamps")
    if (frame.index.date < date.fromisoformat(TEST_START)).any() or (
            frame.index.date > date.fromisoformat(TEST_END)).any():
        raise ValueError("Prediction outside the frozen July–September held-out period")
    if join_canonical:
        for col in ("actual", "baseline"):
            if col not in frame:
                frame[col] = expected.reindex(frame.index)[col]
    for col in ["actual", "predicted", "baseline"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col]).all():
            raise ValueError(f"Nonfinite prediction column: {col}")
        if (frame[col] < 0).any():
            raise ValueError(f"Negative radiation in {col}")
        if (frame[col] > 2000).any():
            raise ValueError(f"Radiation outside the study input range 0–2000 W/m² in {col}")
    if set(frame.index) != set(expected.index):
        raise ValueError("Prediction timestamps must cover every canonical held-out hour exactly once")
    frame = frame.sort_index()
    expected = expected.reindex(frame.index)
    for col in ["actual", "baseline"]:
        if not np.allclose(frame[col], expected[col], rtol=0, atol=1e-6):
            raise ValueError(f"{col} does not match canonical truth / safe issue-time persistence")
    if "baseline_day2" in frame and not np.allclose(pd.to_numeric(frame.baseline_day2),
                                                     expected.baseline_day2, rtol=0, atol=1e-6):
        raise ValueError("Older day-2 persistence does not match canonical values")
    if "climatology" in frame and not np.allclose(pd.to_numeric(frame.climatology),
                                                   expected.climatology, rtol=0, atol=1e-6):
        raise ValueError("Climatology must be fitted to training targets only")
    if "forecast_issue_time" in frame:
        if not frame.forecast_issue_time.astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
            raise ValueError("Forecast issue timestamps require explicit timezone offsets")
        issue = pd.to_datetime(frame.forecast_issue_time, utc=True, errors="raise")
        if not (issue.to_numpy() == pd.to_datetime(expected.forecast_issue_time, utc=True).to_numpy()).all():
            raise ValueError("Forecast issue must be 18:00 local on the preceding date")
    if "baseline_source_time" in frame:
        if not frame.baseline_source_time.astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
            raise ValueError("Baseline source timestamps require explicit timezone offsets")
        sources = pd.to_datetime(frame.baseline_source_time, utc=True, errors="raise")
        if not (sources.to_numpy() == pd.to_datetime(expected.baseline_source_time, utc=True).to_numpy()).all():
            raise ValueError("Baseline source time does not match canonical issue-safe control")
    frame["climatology"] = expected.climatology
    frame["baseline_day2"] = expected.baseline_day2
    frame["baseline_source_time"] = expected.baseline_source_time
    frame["forecast_issue_time"] = expected.forecast_issue_time
    return frame


def validate_metadata(metadata, predictions_path, predictions_sha256=None):
    if not metadata:
        return
    if metadata.get("train_target_before") != TEST_START:
        raise ValueError("Model metadata violates frozen training split")
    last = pd.Timestamp(metadata["train_last_target"])
    if last.tzinfo is None or last.tz_convert(TZ).date() >= date.fromisoformat(TEST_START):
        raise ValueError("Model training targets overlap held-out period")
    audit = metadata.get("leakage_audit", {})
    if audit.get("test_tuning") or audit.get("target_day_realized_weather_features"):
        raise ValueError("Model metadata declares target leakage or test tuning")
    digest = metadata.get("predictions_sha256")
    if digest and digest != (predictions_sha256 or hashlib.sha256(Path(predictions_path).read_bytes()).hexdigest()):
        raise ValueError("Prediction file does not match model metadata identity")


def regression(actual, predicted):
    errors = np.asarray(predicted) - np.asarray(actual)
    return {"mae": float(np.abs(errors).mean()), "rmse": float(np.sqrt(np.mean(errors**2)))}


def score(frame):
    return {"rows": len(frame), **{name: regression(frame.actual, frame[col])
            for name, col in [("model", "predicted"), ("persistence", "baseline"),
                              ("climatology", "climatology"), ("persistence_day2", "baseline_day2")]}}


def confusion(actual, predicted, threshold):
    truth = np.asarray(actual) >= threshold
    flags = np.asarray(predicted) >= threshold
    tp, fp = int((truth & flags).sum()), int((~truth & flags).sum())
    tn, fn = int((~truth & ~flags).sum()), int((truth & ~flags).sum())
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1, "flagged": tp + fp, "actual_positive": tp + fn}


def bootstrap_days(frame, seed=20261002, repeats=2000):
    days = pd.Series(frame.index.date, index=frame.index)
    absolute = pd.DataFrame({"model": np.abs(frame.predicted - frame.actual),
                             "baseline": np.abs(frame.baseline - frame.actual),
                             "baseline_day2": np.abs(frame.baseline_day2 - frame.actual),
                             "climatology": np.abs(frame.climatology - frame.actual)})
    sums = absolute.groupby(days).sum()
    counts = absolute.groupby(days).size().to_numpy()
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(sums), size=(repeats, len(sums)))
    sampled_counts = counts[draws].sum(axis=1)
    model = sums.model.to_numpy()[draws].sum(axis=1) / sampled_counts
    result = {"unit": "local day", "days": len(sums), "repeats": repeats, "seed": seed,
              "interval": "95% percentile paired day bootstrap; seasonal dependence remains"}
    for comparator in ("baseline", "climatology", "baseline_day2"):
        control = sums[comparator].to_numpy()[draws].sum(axis=1) / sampled_counts
        delta = model - control
        relative = 100 * (control - model) / np.maximum(control, 1e-12)
        result[comparator] = {
            "mae_difference_model_minus_control_w_m2": float((absolute.model - absolute[comparator]).mean()),
            "mae_difference_95_ci": np.quantile(delta, [.025, .975]).tolist(),
            "improvement_percent": float(100 * (absolute[comparator].mean() - absolute.model.mean()) /
                                         absolute[comparator].mean()),
            "improvement_percent_95_ci": np.quantile(relative, [.025, .975]).tolist()}
    return result


def make_charts(frame, metrics, directory, importance=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False})
    colors = {"model": "#171717", "persistence": "#626262", "climatology": "#999999"}
    styles = {"model": "-", "persistence": "--", "climatology": ":"}
    markers = {"model": "o", "persistence": "^", "climatology": "s"}
    for key, title, xlabel, filename in [
        ("by_month", "Held-out solar error by month", "Month (2026)", "mae_by_month.png"),
        ("by_hour", "Held-out solar error by local hour", "Hour · Asia/Nicosia", "mae_by_hour.png")]:
        group = metrics[key]
        labels = list(group)
        positions = np.arange(len(labels))
        figure, axes = plt.subplots(figsize=(9, 4.6), layout="constrained")
        for name in colors:
            axes.plot(positions, [group[label][name]["mae"] for label in labels],
                      marker=markers[name], linestyle=styles[name], label=name.title(), color=colors[name])
        axes.set(xticks=positions, xticklabels=labels, ylabel="MAE (W/m²)", xlabel=xlabel, title=title)
        axes.grid(alpha=.2)
        axes.legend()
        figure.savefig(directory / filename, dpi=180)
        plt.close(figure)
    chosen = frame[frame.index.date == frame.index[0].date()]
    figure, axes = plt.subplots(figsize=(9, 4.6), layout="constrained")
    axes.plot(chosen.index.hour, chosen.actual, label="Historical IFS target", color="#171717", linewidth=2)
    for name, col in [("model", "predicted"), ("persistence", "baseline"), ("climatology", "climatology")]:
        axes.plot(chosen.index.hour, chosen[col], label=name.title(), color=colors[name], linestyle=styles[name])
    axes.axhline(metrics["threshold_w_m2"], color="#aaaaaa", linestyle="--", label="Solar proxy threshold")
    axes.set(xlabel="Local hour", ylabel="Radiation (W/m²)",
             title=f"First held-out day · {chosen.index[0].date()} · nominal study issue: prior-day 18:00")
    axes.grid(alpha=.2)
    axes.legend(fontsize=9)
    figure.savefig(directory / "forecast_first_test_day.png", dpi=180)
    plt.close(figure)
    if importance is not None:
        importance = importance.copy()
        importance["gain_percent"] = 100 * importance.gain / importance.gain.sum()
        importance = importance.nlargest(10, "gain").sort_values("gain")
        names = {"shortwave_radiation_lag2": "Radiation 2 days earlier", "shortwave_radiation_lag3": "Radiation 3 days earlier",
                 "hour_cos": "Local hour (cosine)", "issue_day_radiation_mean": "Prior day mean radiation",
                 "year_sin": "Day of year (sine)", "issue_day_cloud_mean": "Prior day mean cloud cover",
                 "year_cos": "Day of year (cosine)", "issue_day_radiation_max": "Prior day maximum radiation",
                 "cloud_cover_at_issue": "Cloud cover at issue", "relative_humidity_2m_at_issue": "Humidity at issue"}
        figure, axes = plt.subplots(figsize=(9, 5), layout="constrained")
        axes.barh([names.get(x, x) for x in importance.feature], importance.gain_percent, color=colors["model"])
        axes.set(title="Reference model feature importance", xlabel="Share of LightGBM split gain (%)")
        figure.savefig(directory / "feature_importance.png", dpi=180)
        plt.close(figure)


def evaluate(predictions_path, weather_path=ROOT / "data/paphos_weather.csv", metadata_path=None,
             output=ROOT / "results", threshold=None, join_canonical=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    predictions_path, weather_path = Path(predictions_path), Path(weather_path)
    inputs = {predictions_path: predictions_path.read_bytes(), weather_path: weather_path.read_bytes()}
    for path in (Path(__file__), ROOT / "model/train.py"):
        inputs[path] = path.read_bytes()
    if metadata_path:
        metadata_path = Path(metadata_path)
        inputs[metadata_path] = metadata_path.read_bytes()
        for path in (ROOT / "model/reference_lightgbm.txt", ROOT / "results/feature_importance.csv"):
            if path.exists():
                inputs[path] = path.read_bytes()
    weather = load_weather(io.BytesIO(inputs[weather_path]))
    expected = expected_predictions(weather)
    supplied = pd.read_csv(io.BytesIO(inputs[predictions_path]))
    frame = validate_predictions(supplied, expected, join_canonical=join_canonical)
    metadata = json.loads(inputs[metadata_path]) if metadata_path else {}
    validate_metadata(metadata, predictions_path, hashlib.sha256(inputs[predictions_path]).hexdigest())
    threshold = threshold if threshold is not None else metadata.get("threshold_w_m2", 600)
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("Radiation threshold must be positive and finite")
    metrics = {
        "model_status": metadata.get("model_status", "Externally supplied predictions; model and feature timing unreviewed"),
        "handoff_provenance": {
            "supplied_columns": list(supplied.columns),
            "canonical_join_requested": join_canonical,
            "canonical_fields_added": [col for col in ("actual", "baseline") if col not in supplied],
            "issue_provenance_supplied": "forecast_issue_time" in supplied,
            "training_metadata_supplied": bool(metadata),
            "source_availability_verified": False,
            "authority": "Actuals and controls are always checked against retained weather. Missing issue times use the study assumption; training metadata alone does not certify source publication availability.",
        },
        "source_kind": "Retrospective Open-Meteo ECMWF IFS gridded historical reconstruction",
        "issue_time": "18:00 Asia/Nicosia on the preceding local date",
        "threshold_w_m2": threshold, "threshold_role": "Solar availability proxy, not measured grid surplus",
        "threshold_selection": metadata.get("threshold_selection", "Fixed scenario threshold; selection provenance unreviewed"),
        "split": {"train_target_before": TEST_START, "test_start": TEST_START, "test_end": TEST_END},
        "rows": len(frame), "days": len(set(frame.index.date)), "units": "W/m²",
        "all": score(frame), "daylight": score(frame[frame.actual > 20]),
        "daylight_definition": "Historical target radiation>20 W/m²; excludes zero-radiation night hours",
        "by_month": {str(month): score(part) for month, part in frame.groupby(frame.index.strftime("%Y-%m"))},
        "by_hour": {str(hour): score(part) for hour, part in frame.groupby(frame.index.hour)},
        "surplus_proxy": {name: confusion(frame.actual, frame[col], threshold) for name, col in
                          [("model", "predicted"), ("persistence", "baseline"), ("climatology", "climatology"),
                           ("persistence_day2", "baseline_day2")]},
        "paired_day_bootstrap": bootstrap_days(frame),
        "feature_timing_audit": metadata.get("leakage_audit", {"status": "Unreviewed external model"}),
        "limitations": ["Historical gridded reconstruction is not sensor ground truth or an archived issue-time forecast.",
                        "Temporal checks do not certify original historical data-publication availability.",
                        "Primary persistence uses latest available same local hour: day-1 for00–18 and day-2 for19–23.",
                        "Hour18 source ends at the issue cutoff; zero reporting latency is assumed, not validated.",
                        "No measured grid surplus, curtailment, tariff, water-demand or plant-benefit labels.",
                        "July–September results do not establish cloudy-winter accuracy.",
                        "Any scheduling savings are illustrative outcomes under separate declared assumptions."]}
    metrics["paired_day_bootstrap_daylight"] = bootstrap_days(frame[frame.actual > 20])
    cloud = weather.reindex(frame.index).cloud_cover
    metrics["cloudiness_daylight"] = {}
    for name, lower, upper in [("low_0_to_20_percent", 0, 20), ("medium_20_to_60_percent", 20, 60),
                               ("high_60_to_100_percent", 60, 101)]:
        part = frame[(frame.actual > 20) & (cloud >= lower) & (cloud < upper)]
        metrics["cloudiness_daylight"][name] = score(part) if len(part) else {"rows": 0}
    metrics["cloudiness_strata_role"] = "Realized target cloud cover is used only for error diagnosis, never model features"
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    rows = []
    for scope, group in [("all", metrics["all"]), ("daylight", metrics["daylight"])]:
        for model in ("model", "persistence", "climatology", "persistence_day2"):
            rows.append({"scope": scope, "group": "all", "comparator": model,
                         "rows": group["rows"], **group[model]})
    for scope in ("by_month", "by_hour"):
        for key, group in metrics[scope].items():
            for model in ("model", "persistence", "climatology", "persistence_day2"):
                rows.append({"scope": scope, "group": key, "comparator": model,
                             "rows": group["rows"], **group[model]})
    pd.DataFrame(rows).to_csv(output / "results.csv", index=False)
    importance_bytes = inputs.get(ROOT / "results/feature_importance.csv")
    importance = pd.read_csv(io.BytesIO(importance_bytes)) if importance_bytes is not None else None
    make_charts(frame, metrics, output / "charts", importance)
    snapshot_dir = output / "input-snapshots"
    snapshot_dir.mkdir(exist_ok=True)
    snapshots = {}
    for path in (predictions_path, weather_path, *([metadata_path] if metadata_path else [])):
        digest = hashlib.sha256(inputs[path]).hexdigest()
        destination = snapshot_dir / (digest + path.suffix)
        destination.write_bytes(inputs[path])
        snapshots[str(path)] = str(destination.relative_to(output))
    manifest = {
        "inputs": {str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path):
                   hashlib.sha256(data).hexdigest() for path, data in inputs.items()},
        "input_snapshots": snapshots,
        "input_identity_role": "Exact bytes captured before parsing; predictions, weather and metadata snapshots retained even if source paths later change",
        "python": sys.version, "platform": platform.platform(), "invocation": sys.argv,
        "rows": len(frame), "first_target": frame.index.min().isoformat(),
        "last_target": frame.index.max().isoformat(), "threshold_w_m2": threshold,
        "outputs": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [output / "metrics.json", output / "results.csv", *(output / "charts").glob("*.png")]
                    if path.is_file()}}
    (output / "evaluation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"rows": len(frame), "days": metrics["days"], "threshold_w_m2": threshold,
                      "all": metrics["all"], "daylight": metrics["daylight"],
                      "surplus_proxy": metrics["surplus_proxy"]}))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=ROOT / "data/test_predictions.csv")
    parser.add_argument("--weather", type=Path, default=ROOT / "data/paphos_weather.csv")
    parser.add_argument("--model-metadata", type=Path)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--join-canonical", action="store_true", help="Explicitly join missing actual/baseline fields from retained weather; supplied values are still checked")
    args = parser.parse_args()
    evaluate(args.predictions, args.weather, args.model_metadata, args.output, args.threshold, args.join_canonical)
