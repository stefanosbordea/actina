"""Matched frozen v2 context heads with a strictly causal observation stream."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "2"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "v2-017"
spec = importlib.util.spec_from_file_location("method017", PREVIOUS / "run.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
h, np, pd = m.h, m.np, m.pd
import context
ARMS = ("core", "expanded")


def verify():
    lock = json.loads((HERE / "lock.json").read_text())
    for name, expected in lock["source_sha256"].items():
        assert h.sha(ROOT / name) == expected, name


def issued_history(history):
    valid = history["v2_prediction"].notna()
    issued = pd.DatetimeIndex(pd.to_datetime(history.loc[valid, "v2_source_origin"]))
    assert issued.equals(history.index[valid] - h.DAY), "History prediction is not from target−24h origin"
    assert history.index.is_unique and history.index.is_monotonic_increasing


def features(frame, ctx, arm):
    core = m.features(frame, "expanded")
    if arm == "core":
        return core
    assert arm == "expanded" and ctx.index.equals(frame.index)
    return pd.concat([core, ctx], axis=1)


def check_prior_inference(probability, prior):
    assert np.allclose(probability, prior, rtol=0, atol=1e-12, equal_nan=True), "Unchanged matched control no longer reproduces017"


def run(out):
    verify()
    manifest = json.loads((HERE / "inputs/manifest.json").read_text())
    upstream_audit = json.loads((HERE.parent / "v2-016/inputs/source-audit.json").read_text())
    assert manifest["upstream_weather_sha256"] == upstream_audit["source_sha256"]["data/paphos_weather_datav2.csv"]
    train = h.load_frame(PREVIOUS / "inputs/train.csv", "origin")
    validation = h.load_frame(PREVIOUS / "inputs/validation.csv", "origin")
    history = h.load_frame(HERE / "inputs/history-predictions.csv", "target_time")
    issued_history(history)
    observations = h.load_frame(HERE / "inputs/observations-training.csv", "target_time")
    assert observations.index.max() < train.index.max()
    ctx, train_audit = context.build(train.index, history, observations)
    ctx.to_csv(out / "training-context.csv", index_label="origin")
    train_audit.to_csv(out / "training-context-coverage.csv", index_label="origin")
    assert len(train) == 10675 and len(validation) == 3566
    truth = train["target"].to_numpy() > 600
    held_union = train["fold"].to_numpy() >= 3
    choices, models, fits = {}, {}, []
    for arm in ARMS:
        x = features(train, ctx, arm)
        forward = pd.Series(np.nan, index=train.index)
        for fold in range(3, 7):
            held = train["fold"] == fold
            first = train.index[held][0]
            fit = (train["fold"].to_numpy() < fold) & h.permitted(train.index, first)
            assert (train.index[fit] + h.DAY).max() < first
            model = h.fit_head("boosted", x.loc[fit], truth[fit])
            model.booster_.save_model(str(out / f"{arm}-fold{fold}.txt"))
            forward.loc[held] = model.predict_proba(x.loc[held])[:, 1]
            pd.DataFrame({"origin": train.index.astype(str), "target_time": (train.index + h.DAY).astype(str),
                "fit": np.asarray(fit, dtype=int), "held": held.to_numpy(dtype=int)}).to_csv(
                    out / f"{arm}-fold{fold}-membership.csv", index=False)
            fits.append(dict(arm=arm, fold=fold, fit_rows=int(fit.sum()), held_rows=int(held.sum()),
                fit_target_last=str((train.index[fit] + h.DAY).max()), held_origin_first=str(first)))
        assert np.array_equal(forward.notna().to_numpy(), held_union)
        choice, grid = m.select(truth[held_union], forward.to_numpy()[held_union],
                               train["ecmwf_day2"].to_numpy()[held_union] > 600)
        choices[arm] = choice
        pd.DataFrame(grid).to_csv(out / f"{arm}-thresholds.csv", index=False)
        pd.DataFrame({"origin": train.index.astype(str), "fold": train["fold"].to_numpy(),
            "truth": truth.astype(int), "forward_probability": forward.to_numpy()}).to_csv(
                out / f"{arm}-forward.csv", index=False)
        if arm == "core":
            old = h.load_frame(PREVIOUS / "result/expanded-forward.csv", "origin")
            assert old.index.equals(train.index)
            check_prior_inference(forward.to_numpy(), old["forward_probability"].to_numpy())
            expected = json.loads((PREVIOUS / "result/summary.json").read_text())["selected_training_thresholds"]["expanded"]
            assert choice == expected
        if choice is not None:
            models[arm] = h.fit_head("boosted", x, truth)
            models[arm].booster_.save_model(str(out / f"{arm}-final.txt"))
            pd.DataFrame({"feature": x.columns,
                "gain_importance": models[arm].booster_.feature_importance(importance_type="gain"),
                "split_importance": models[arm].booster_.feature_importance(importance_type="split")}).to_csv(
                    out / f"{arm}-importance.csv", index=False)
        h.log(f"{arm}: training-only threshold {choice}")
    frozen_models = {p.name: h.sha(p) for p in out.iterdir() if p.suffix == ".txt"}
    training_context_hashes = {name: h.sha(out / name) for name in ("training-context.csv", "training-context-coverage.csv")}
    h.save(out / "head-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        lock_sha256=h.sha(HERE / "lock.json"), selected_training_thresholds=choices, fits=fits,
        model_sha256=frozen_models, training_context_sha256=training_context_hashes,
        note="Head fits and thresholds complete. Validation observation stream has not been loaded by this runner."))
    h.log("HEAD_FREEZE saved. Loading validation observations for strictly prior context only.")
    stream = h.load_frame(HERE / "inputs/observations-validation-stream.csv", "target_time")
    assert stream.index.min() >= train.index.max() and stream.index.max() < validation.index.max()
    observed = pd.concat([observations, stream])
    assert observed.index.is_unique and observed.index.is_monotonic_increasing
    validation_ctx, validation_audit = context.build(validation.index, history, observed)
    validation_ctx.to_csv(out / "validation-context.csv", index_label="origin")
    validation_audit.to_csv(out / "validation-context-coverage.csv", index_label="origin")
    decisions = pd.DataFrame({"base_prediction": validation["base_prediction"]}, index=validation.index)
    for arm, model in models.items():
        p = model.predict_proba(features(validation, validation_ctx, arm))[:, 1]
        assert np.isfinite(p).all()
        decisions[f"{arm}_probability"] = p
        decisions[f"{arm}_call"] = (p > choices[arm]["threshold"]).astype(int)
    prior = h.load_frame(PREVIOUS / "result/validation-decisions.csv", "origin")
    assert prior.index.equals(validation.index)
    check_prior_inference(decisions["core_probability"].to_numpy(), prior["expanded_probability"].to_numpy())
    assert np.array_equal(decisions["core_call"], prior["expanded_call"])
    decisions.to_csv(out / "validation-decisions.csv", index_label="origin")
    frozen_decisions = {name: h.sha(out / name) for name in
        ("validation-decisions.csv", "validation-context.csv", "validation-context-coverage.csv")}
    h.save(out / "decision-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        head_freeze_sha256=h.sha(out / "head-freeze.json"), prediction_sha256=frozen_decisions,
        note="Each context used only t in [origin−336h,origin). Full validation scoring starts after this freeze."))
    assert all(h.sha(out / name) == digest for name, digest in frozen_models.items())
    h.log("DECISION_FREEZE saved. Scoring full validation reference now.")
    supplied = h.load_frame(PREVIOUS / "inputs/cv_predictions_v2.csv")
    original = h.load_frame(PREVIOUS / "inputs/original-validation.csv")
    fixed008 = h.load_frame(PREVIOUS / "inputs/fixed008-validation.csv", "feature_time")
    for frame in (supplied, original, fixed008):
        assert frame.index.equals(validation.index)
    assert np.array_equal(supplied["actual"], original["actual"])
    assert np.array_equal(supplied["actual"], fixed008["weather_actual_w_m2"])
    actual = supplied["actual"].to_numpy()
    truth = actual > 600
    radiation = dict(base_refit=validation["base_prediction"].to_numpy(),
        supplied_v2_600=supplied["predicted"].to_numpy(), supplied_v2_562=supplied["predicted"].to_numpy(),
        supplied_raw_day1=supplied["forecast"].to_numpy(), retained_raw_day2=validation["ecmwf_day2"].to_numpy(),
        persistence=supplied["baseline"].to_numpy())
    calls = {name: values > (562 if name == "supplied_v2_562" else 600) for name, values in radiation.items()}
    calls["fixed008"] = fixed008["predicted_positive"].to_numpy(dtype=bool)
    calls.update({arm: decisions[f"{arm}_call"].to_numpy(dtype=bool) for arm in models})
    metrics = {}
    for name, call in calls.items():
        row = h.counts(truth, call)
        if name in radiation:
            row.update(h.regression(actual, radiation[name]))
        elif name in models:
            row.update(h.probability_metrics(truth, decisions[f"{name}_probability"].to_numpy()))
            row["unchanged_base_radiation_errors"] = h.regression(actual, radiation["base_refit"])
        metrics[name] = row
    assert metrics["fixed008"]["f1_exact"] == "271/299" and metrics["core"]["f1_exact"] == "274/303"
    record = decisions.copy()
    record["actual"] = actual
    record["target_time"] = (validation.index + h.DAY).astype(str)
    for name, call in calls.items():
        record[f"call_{name}"] = call.astype(int)
    for name, values in radiation.items():
        record[f"radiation_{name}"] = values
    record.to_csv(out / "validation-evaluation.csv", index_label="origin")
    h.save(out / "day-bootstrap.json", m.intervals(validation.index, truth, calls, models))
    comparisons = {}
    for arm in ARMS:
        if arm not in models:
            comparisons[arm] = dict(status="inadmissible")
            continue
        comparisons[arm] = dict(status="evaluated",
            user_gate=Fraction(metrics[arm]["f1_exact"]) > Fraction(metrics["fixed008"]["f1_exact"]) and metrics[arm]["fp"] <= metrics["fixed008"]["fp"],
            deltas={control: {key: h.metric_difference(metrics[arm][key], metrics[control][key])
                             for key in ("tp", "fp", "fn", "precision", "recall", "f1")}
                    for control in ("core", "base_refit", "fixed008", "supplied_v2_600", "supplied_v2_562") if control != arm})
    coverage = {split: {model: dict(minimum=int(table[f"{model}_count"].min()),
        maximum=int(table[f"{model}_count"].max()), zero_windows=int((table[f"{model}_count"] == 0).sum()),
        partial_windows=int((table[f"{model}_count"] < 336).sum())) for model in ("v2", "ecmwf")}
        for split, table in (("train", train_audit), ("validation", validation_audit))}
    h.save(out / "summary.json", dict(status="completed", validation_hours=len(actual), metrics=metrics,
        selected_training_thresholds=choices, comparisons=comparisons, coverage=coverage,
        note="Sequential reused validation with strictly past observed-error features. No base refit, validation threshold selection, test scoring or promotion."))
    assert all(h.sha(out / name) == digest for name, digest in {**frozen_models, **frozen_decisions, **training_context_hashes}.items())
    verify()
    h.log(json.dumps(dict(metrics=metrics, comparisons=comparisons), allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="result")
    args = parser.parse_args()
    out = HERE / args.out
    assert out.parent == HERE and out.name not in ("inputs", "review")
    verify()
    out.mkdir(exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("1800-second budget exceeded")))
    signal.alarm(1800)
    h.save(out / "environment.json", dict(command=sys.argv, started_at_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version, versions={name: h.version(name) for name in ("numpy", "pandas", "lightgbm", "scikit-learn")},
        thread_cap=2, lock_sha256=h.sha(HERE / "lock.json")))
    status, failure = "completed", None
    try:
        with h.threadpool_limits(limits=2):
            run(out)
    except BaseException as error:
        status, failure = "failed", repr(error)
        (out / "failure.txt").write_text(traceback.format_exc())
        raise
    finally:
        signal.alarm(0)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        h.save(out / "completion.json", dict(status=status, error=failure,
            completed_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - start,
            cpu_seconds=time.process_time() - cpu, peak_rss_bytes=rss,
            output_sha256={p.name: h.sha(p) for p in sorted(out.iterdir()) if p.is_file()}))


if __name__ == "__main__":
    main()
