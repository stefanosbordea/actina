"""Bounded chronological v2-dependent event post-processing experiment."""
import os
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "2"
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import resource
import signal
import sys
import time
import traceback

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor, early_stopping
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs"
BASE_FEATURES = ["temperature_2m", "shortwave_radiation", "relative_humidity_2m", "cloud_cover",
                 "nwp_radiation", "nwp_cloud", "radiation_yesterday", "hour", "month"]
HEAD_FEATURES = ["base_margin", "nwp_minus_base", "nwp_cloud", "margin_cloud",
                 "hour_sin", "hour_cos", "month_sin", "month_cos"]
STARTS = pd.to_datetime(["2024-07-01", "2024-10-01", "2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01"])
TRAIN_END = pd.Timestamp("2025-12-03 18:00")
VALIDATION_START = pd.Timestamp("2025-12-04 19:00")
VALIDATION_END = pd.Timestamp("2026-05-02 08:00")
DAY = pd.Timedelta(hours=24)
ARMS = ("logistic", "boosted")
COMMON = dict(n_jobs=2, verbosity=-1, deterministic=True, force_col_wise=True, random_state=0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n")


def log(message):
    print(datetime.now(timezone.utc).isoformat(), message, flush=True)


def load_frame(path, time_column="time"):
    frame = pd.read_csv(path, index_col=time_column, parse_dates=[time_column])
    assert frame.index.is_monotonic_increasing and frame.index.is_unique
    assert frame.index.tz is None and len(frame)
    return frame


def permitted(index, held_origin):
    return index + DAY < held_origin


def inner_split(index):
    stop = index >= index[-1] - pd.Timedelta(days=28) + pd.Timedelta(hours=1)
    stop_first = index[stop][0]
    fit = permitted(index, stop_first)
    assert fit.any() and stop.any() and not np.any(fit & stop)
    assert (index[fit] + DAY).max() < stop_first
    return fit, stop


def counts(actual, calls):
    actual, calls = np.asarray(actual, dtype=bool), np.asarray(calls, dtype=bool)
    assert actual.shape == calls.shape and actual.size
    tp = int(np.sum(actual & calls))
    fp = int(np.sum(~actual & calls))
    fn = int(np.sum(actual & ~calls))
    tn = int(np.sum(~actual & ~calls))
    def ratio(n, d):
        return None if not d else float(Fraction(n, d))
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn),
                f1=ratio(2 * tp, 2 * tp + fp + fn),
                f1_exact=None if not 2 * tp + fp + fn else str(Fraction(2 * tp, 2 * tp + fp + fn)))


def select_threshold(actual, probability):
    assert np.isfinite(probability).all() and np.all((probability >= 0) & (probability <= 1))
    rows = [dict(tick=tick, threshold=tick / 200, **counts(actual, probability > tick / 200))
            for tick in range(10, 191)]
    candidates = [row for row in rows if row["f1_exact"] is not None]
    assert candidates
    chosen = max(candidates, key=lambda row: (Fraction(row["f1_exact"]), -abs(row["tick"] - 100), row["tick"]))
    return chosen, rows


def head_features(base, frame):
    margin = (np.asarray(base) - 600) / 100
    cloud = frame["nwp_cloud"].to_numpy() / 100
    hour = 2 * np.pi * frame["hour"].to_numpy() / 24
    month = 2 * np.pi * (frame["month"].to_numpy() - 1) / 12
    return pd.DataFrame(np.column_stack([margin, (frame["nwp_radiation"].to_numpy() - base) / 100,
        cloud, margin * cloud, np.sin(hour), np.cos(hour), np.sin(month), np.cos(month)]),
        index=frame.index, columns=HEAD_FEATURES)


def head_model(arm):
    if arm == "logistic":
        return LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, tol=1e-8,
                                  class_weight=None, random_state=0)
    assert arm == "boosted"
    return LGBMClassifier(n_estimators=150, learning_rate=0.03, max_depth=3, num_leaves=7,
                         min_child_samples=100, reg_lambda=10, objective="binary", **COMMON)


def fit_head(arm, features, truth):
    assert len(np.unique(truth)) == 2, "Head training must contain both classes"
    model = head_model(arm).fit(features, truth)
    if arm == "logistic":
        assert int(model.n_iter_.max()) < 1000, "Logistic head did not converge"
    return model


def fit_base(frame, label, out):
    fit, stop = inner_split(frame.index)
    selector = LGBMRegressor(n_estimators=1000, learning_rate=0.05, metric="l1", **COMMON)
    selector.fit(frame.loc[fit, BASE_FEATURES], frame.loc[fit, "target"],
                 eval_set=[(frame.loc[stop, BASE_FEATURES], frame.loc[stop, "target"])],
                 callbacks=[early_stopping(50, verbose=False)])
    trees = int(selector.best_iteration_)
    assert 1 <= trees <= 1000
    model = LGBMRegressor(n_estimators=trees, learning_rate=0.05, metric="l1", **COMMON)
    model.fit(frame[BASE_FEATURES], frame["target"])
    selector.booster_.save_model(str(out / f"{label}-inner.txt"))
    model.booster_.save_model(str(out / f"{label}-base.txt"))
    membership = pd.DataFrame({"origin": frame.index.astype(str), "target_time": (frame.index + DAY).astype(str),
                               "inner_fit": fit.astype(int), "inner_stop": stop.astype(int)})
    membership.to_csv(out / f"{label}-training-membership.csv", index=False)
    info = dict(label=label, outer_rows=len(frame), outer_origin_first=str(frame.index[0]),
                outer_origin_last=str(frame.index[-1]), outer_target_last=str(frame.index[-1] + DAY),
                inner_fit_rows=int(fit.sum()), inner_stop_rows=int(stop.sum()),
                inner_fit_target_last=str(frame.index[fit][-1] + DAY),
                inner_stop_origin_first=str(frame.index[stop][0]), selected_trees=trees)
    log(f"{label}: {len(frame)} train rows, {trees} trees")
    return model, info


def regression(actual, predicted):
    error = np.asarray(predicted) - np.asarray(actual)
    return dict(mae_w_m2=float(np.mean(np.abs(error))), rmse_w_m2=float(np.sqrt(np.mean(error ** 2))),
                bias_w_m2=float(np.mean(error)))


def metric_difference(first, second):
    return None if first is None or second is None else first - second


def probability_metrics(truth, probability):
    probability = np.asarray(probability)
    clipped = np.clip(probability, 1e-15, 1 - 1e-15)
    return dict(brier=float(np.mean((probability - truth) ** 2)),
                log_loss=float(-np.mean(truth * np.log(clipped) + (~truth) * np.log1p(-clipped))))


def bootstrap(index, truth, calls):
    dates = (index + DAY).normalize()
    unique = dates.unique()
    arrays = {}
    for name, call in calls.items():
        arrays[name] = np.array([[np.sum(truth[dates == date] & call[dates == date]),
                                 np.sum(~truth[dates == date] & call[dates == date]),
                                 np.sum(truth[dates == date] & ~call[dates == date])]
                                for date in unique], dtype=np.int64)
    rng = np.random.default_rng(16016)
    draws = rng.integers(0, len(unique), size=(2000, len(unique)))
    f1 = {}
    for name, array in arrays.items():
        totals = array[draws].sum(axis=1)
        denominator = 2 * totals[:, 0] + totals[:, 1] + totals[:, 2]
        f1[name] = np.divide(2 * totals[:, 0], denominator, where=denominator != 0,
                             out=np.full(len(denominator), np.nan))
    comparisons = {}
    for arm in ARMS:
        for control in ("base_refit", "supplied_v2_600", "supplied_v2_562", "fixed008"):
            difference = f1[arm] - f1[control]
            finite = difference[np.isfinite(difference)]
            comparisons[f"{arm}_minus_{control}"] = dict(
                lower_025=float(np.quantile(finite, 0.025)) if len(finite) else None,
                upper_975=float(np.quantile(finite, 0.975)) if len(finite) else None,
                undefined_replicates=int(np.sum(~np.isfinite(difference))))
    return dict(seed=16016, replicates=2000, target_day_blocks=len(unique), comparisons=comparisons,
                scope="Paired descriptive day-block intervals on reused validation, without selection-bias correction.")


def verify_lock():
    lock = json.loads((HERE / "lock.json").read_text())
    for name, expected in lock["sha256"].items():
        assert sha(HERE / name) == expected, f"Frozen input changed: {name}"
    return lock


def run(out):
    lock = verify_lock()
    train = load_frame(INPUTS / "train.csv")
    validation = load_frame(INPUTS / "validation-features.csv")
    assert list(train.columns) == BASE_FEATURES + ["target"]
    assert list(validation.columns) == BASE_FEATURES
    assert len(train) == 16444 and train.index[-1] == TRAIN_END
    assert len(validation) == 3566 and validation.index[0] == VALIDATION_START and validation.index[-1] == VALIDATION_END
    assert np.isfinite(train.to_numpy()).all() and np.isfinite(validation.to_numpy()).all()
    for frame in (train, validation):
        assert np.all(frame.index[1:] - frame.index[:-1] == pd.Timedelta(hours=1))
    source_audit = json.loads((INPUTS / "source-audit.json").read_text())
    assert source_audit["status"] == "PASS"
    assert all(not value["target_shift_not_24h"] for value in source_audit["splits"].values())
    assert (train.index + DAY).max() < validation.index.min()
    assert not train.index.intersection(validation.index).size
    oof_rows, fits = [], []
    for number, start in enumerate(STARTS):
        end = STARTS[number + 1] if number + 1 < len(STARTS) else TRAIN_END + pd.Timedelta(hours=1)
        held = train.loc[(train.index >= start) & (train.index < end)]
        eligible = train.loc[permitted(train.index, held.index[0])]
        assert eligible.index[-1] + DAY < held.index[0]
        model, info = fit_base(eligible, f"fold{number + 1}", out)
        prediction = np.maximum(model.predict(held[BASE_FEATURES]), 0)
        block = held.copy()
        block["base_prediction"] = prediction
        block["fold"] = number + 1
        oof_rows.append(block)
        info.update(held_origin_first=str(held.index[0]), held_origin_last=str(held.index[-1]), held_rows=len(held))
        fits.append(info)
        pd.DataFrame(fits).to_csv(out / "base-folds.csv", index=False)
    oof = pd.concat(oof_rows)
    assert oof.index.is_unique and oof.index.max() <= TRAIN_END
    oof.to_csv(out / "base-oof.csv", index_label="origin")
    meta_x = head_features(oof["base_prediction"].to_numpy(), oof)
    meta_y = (oof["target"].to_numpy() > 600)
    selected, meta_receipts, final_heads = {}, [], {}
    for arm in ARMS:
        forward = pd.Series(np.nan, index=oof.index)
        for fold in range(3, 7):
            held = oof["fold"] == fold
            first = oof.index[held][0]
            fit = (oof["fold"].to_numpy() < fold) & permitted(oof.index, first)
            assert (oof.index[fit] + DAY).max() < first
            model = fit_head(arm, meta_x.loc[fit], meta_y[fit])
            forward.loc[held] = model.predict_proba(meta_x.loc[held])[:, 1]
            membership = pd.DataFrame({"origin": oof.index.astype(str), "target_time": (oof.index + DAY).astype(str),
                                       "fit": np.asarray(fit, dtype=int), "held": held.to_numpy(dtype=int)})
            membership.to_csv(out / f"{arm}-fold{fold}-membership.csv", index=False)
            meta_receipts.append(dict(arm=arm, held_fold=fold, fit_rows=int(fit.sum()),
                fit_target_last=str((oof.index[fit] + DAY).max()), held_origin_first=str(first), held_rows=int(held.sum())))
        valid = forward.notna().to_numpy()
        chosen, candidates = select_threshold(meta_y[valid], forward.to_numpy()[valid])
        selected[arm] = chosen
        pd.DataFrame(candidates).to_csv(out / f"{arm}-training-thresholds.csv", index=False)
        pd.DataFrame({"origin": oof.index.astype(str), "fold": oof["fold"].to_numpy(), "truth": meta_y.astype(int),
                      "forward_probability": forward.to_numpy()}).to_csv(out / f"{arm}-forward.csv", index=False)
        final_heads[arm] = fit_head(arm, meta_x, meta_y)
        log(f"{arm}: training-selected threshold {chosen['threshold']}, forward F1 {chosen['f1_exact']}")
    final_base, final_info = fit_base(train, "final", out)
    base_prediction = np.maximum(final_base.predict(validation[BASE_FEATURES]), 0)
    validation_head_x = head_features(base_prediction, validation)
    decisions = pd.DataFrame({"base_prediction": base_prediction}, index=validation.index)
    head_parameters = {}
    for arm, model in final_heads.items():
        probability = model.predict_proba(validation_head_x)[:, 1]
        assert np.isfinite(probability).all()
        decisions[f"{arm}_probability"] = probability
        decisions[f"{arm}_call"] = (probability > selected[arm]["threshold"]).astype(int)
        if arm == "logistic":
            head_parameters[arm] = dict(features=HEAD_FEATURES, coefficients=model.coef_[0].tolist(),
                                         intercept=float(model.intercept_[0]), classes=model.classes_.tolist())
            save(out / "logistic-model.json", head_parameters[arm])
        else:
            model.booster_.save_model(str(out / "boosted-head.txt"))
            head_parameters[arm] = dict(features=HEAD_FEATURES, parameters=model.get_params())
            pd.DataFrame({"feature": HEAD_FEATURES,
                "split_importance": model.booster_.feature_importance(importance_type="split"),
                "gain_importance": model.booster_.feature_importance(importance_type="gain")}).to_csv(
                    out / "boosted-head-importance.csv", index=False)
    decisions.to_csv(out / "validation-decisions.csv", index_label="origin")
    frozen_files = {name: sha(out / name) for name in
                    ("final-base.txt", "logistic-model.json", "boosted-head.txt", "validation-decisions.csv")}
    save(out / "policy-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
         lock_sha256=sha(HERE / "lock.json"), selected_training_thresholds=selected, base_fits=fits,
         final_base=final_info, head_fits=meta_receipts, heads=head_parameters,
         frozen_prediction_files_sha256=frozen_files,
         validation_decisions_sha256=sha(out / "validation-decisions.csv"),
         statement="All fits, thresholds, radiation predictions and event decisions frozen before parsing validation outcomes."))
    log("Validation decision freeze saved. Loading fixed validation references for one scoring pass.")
    assert all(sha(out / name) == expected for name, expected in frozen_files.items())

    # These outcome-bearing files are parsed only after the saved policy freeze.
    supplied = load_frame(INPUTS / "cv_predictions_v2.csv")
    original = load_frame(INPUTS / "original-validation.csv")
    fixed008 = load_frame(INPUTS / "fixed008-validation.csv", "feature_time")
    day2 = load_frame(INPUTS / "retained-day2-validation.csv", "feature_time")
    for frame in (supplied, original, fixed008, day2):
        assert frame.index.equals(validation.index)
    assert np.array_equal(supplied["actual"], original["actual"])
    assert np.array_equal(supplied["baseline"], original["baseline"])
    assert np.array_equal(supplied["actual"], fixed008["weather_actual_w_m2"])
    assert np.array_equal(supplied["forecast"], validation["nwp_radiation"])
    assert pd.DatetimeIndex(pd.to_datetime(fixed008["target_time"])).equals(validation.index + DAY)
    assert set(fixed008["predicted_positive"]) <= {0, 1}
    actual = supplied["actual"].to_numpy()
    truth = actual > 600
    radiation = dict(base_refit=base_prediction, supplied_v2_600=supplied["predicted"].to_numpy(),
        supplied_v2_562=supplied["predicted"].to_numpy(), supplied_raw_day1=supplied["forecast"].to_numpy(),
        retained_raw_day2=day2["nwp_day2_radiation"].to_numpy(), persistence=supplied["baseline"].to_numpy())
    calls = {name: values > (562 if name == "supplied_v2_562" else 600) for name, values in radiation.items()}
    calls["fixed008"] = fixed008["predicted_positive"].to_numpy(dtype=bool)
    for arm in ARMS:
        calls[arm] = decisions[f"{arm}_call"].to_numpy(dtype=bool)
    metrics = {}
    for name, call in calls.items():
        row = counts(truth, call)
        if name in radiation:
            row.update(regression(actual, radiation[name]))
        if name in ARMS:
            row["unchanged_base_radiation_errors"] = regression(actual, base_prediction)
            row.update(probability_metrics(truth, decisions[f"{name}_probability"].to_numpy()))
        metrics[name] = row
    assert metrics["fixed008"]["f1_exact"] == "271/299"
    assert metrics["supplied_v2_600"]["f1_exact"] == "524/593"
    assert metrics["supplied_v2_562"]["f1_exact"] == "41/46"
    assert metrics["retained_raw_day2"]["f1_exact"] == "536/595"
    record = decisions.copy()
    record["target_time"] = (validation.index + DAY).astype(str)
    record["actual"] = actual
    for name, call in calls.items():
        record[f"call_{name}"] = call.astype(int)
    for name, values in radiation.items():
        record[f"radiation_{name}"] = values
    record.to_csv(out / "validation-evaluation.csv", index_label="origin")
    uncertainty = bootstrap(validation.index, truth, calls)
    save(out / "day-bootstrap.json", uncertainty)
    comparison = {}
    for arm in ARMS:
        comparison[arm] = dict(exceeds_all_retained_f1=all(Fraction(metrics[arm]["f1_exact"]) > Fraction(metrics[control]["f1_exact"])
                    for control in ("fixed008", "supplied_v2_600", "supplied_v2_562")),
                    versus={control: {metric: metric_difference(metrics[arm][metric], metrics[control][metric]) for metric in ("precision", "recall", "f1")}
                            for control in ("base_refit", "fixed008", "supplied_v2_600", "supplied_v2_562")})
    save(out / "summary.json", dict(status="completed", validation_hours=len(actual), metrics=metrics,
         training_thresholds=selected, comparison=comparison, uncertainty="day-bootstrap.json",
         note="Exploratory reused validation. No test scoring, no new thresholds selected from validation, no automatic promotion."))
    log(json.dumps(dict(metrics=metrics, comparison=comparison), allow_nan=False))
    assert all(sha(out / name) == expected for name, expected in frozen_files.items())
    verify_lock()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="result")
    args = parser.parse_args()
    out = HERE / args.out
    assert out.parent == HERE and out.name not in ("inputs", "review")
    verify_lock()
    out.mkdir(exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("1800-second budget exceeded")))
    signal.alarm(1800)
    environment = dict(python=sys.version, platform=platform.platform(),
        versions={name: version(name) for name in ("numpy", "pandas", "lightgbm", "scikit-learn", "threadpoolctl")},
        thread_environment={key: os.environ[key] for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")},
        command=sys.argv, started_at_utc=datetime.now(timezone.utc).isoformat(), lock_sha256=sha(HERE / "lock.json"))
    save(out / "environment.json", environment)
    status, failure = "completed", None
    try:
        with threadpool_limits(limits=2):
            run(out)
    except BaseException as error:
        status, failure = "failed", repr(error)
        (out / "failure.txt").write_text(traceback.format_exc())
        raise
    finally:
        signal.alarm(0)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            rss *= 1024
        save(out / "completion.json", dict(status=status, error=failure,
            completed_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - start,
            cpu_seconds=time.process_time() - cpu, peak_rss_bytes=rss,
            output_sha256={path.name: sha(path) for path in sorted(out.iterdir()) if path.is_file()}))


if __name__ == "__main__":
    main()
