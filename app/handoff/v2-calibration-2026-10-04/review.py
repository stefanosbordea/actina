"""Independently verify the completed validation scan. Never read test outcomes."""
import argparse
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = "85097a560769ad8a1459ce55f0b3a4c301202405"
EVAL_TREE = "eval/.gitkeep\neval/cv_predictions.csv\neval/cv_predictions_v2.csv\neval/explore.py\neval/plots/radiation_average.png\neval/results.ipynb\neval/schedule_hourly.csv\neval/test_predictions.csv\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def close(observed, expected):
    assert math.isclose(float(observed), float(expected), rel_tol=0, abs_tol=1e-12), (observed, expected)


def count(truth, calls):
    result = dict(tp=0, fp=0, fn=0, tn=0)
    assert len(truth) == len(calls) and truth
    for actual, called in zip(truth, calls):
        result[("tp" if called else "fn") if actual else ("fp" if called else "tn")] += 1
    tp, fp, fn = (result[key] for key in ("tp", "fp", "fn"))
    ratios = dict(precision=Fraction(tp, tp + fp), recall=Fraction(tp, tp + fn),
                  f1=Fraction(2 * tp, 2 * tp + fp + fn))
    return dict(result, **{key: float(value) for key, value in ratios.items()},
                f1_exact=str(ratios["f1"]))


def verify_metrics(saved, expected):
    for key in ("tp", "fp", "fn", "tn"):
        assert int(saved[key]) == expected[key], (key, saved, expected)
    for key in ("precision", "recall", "f1"):
        close(saved[key], expected[key])
    assert Fraction(saved["f1_exact"]) == Fraction(expected["f1_exact"])


def inspect():
    protocol = HERE / "PROTOCOL.md"
    pins = json.loads(protocol.read_text().split("```json\n", 1)[1].split("```", 1)[0])
    selection = read_json(HERE / "validation-selection.json")
    receipt = read_json(HERE / "run-receipt.json")
    assert pins == selection["sources"]["files"]
    assert sha(protocol) == selection["sources"]["protocol_sha256"] == receipt["pre_execution_protocol_sha256"]
    for name, expected in pins.items():
        assert sha(ROOT / name) == expected, name
    assert all(run["exit_code"] == 0 for run in receipt["runs"])
    for run, name in zip(receipt["runs"], ("fixtures.log", "validation-scan.log")):
        assert sha(HERE / name) == run["log_sha256"], name
    for name, expected in receipt["output_sha256"].items():
        assert sha(HERE / name) == expected, name
    assert sha(HERE / "validation-table.csv") == selection["validation_table_sha256"]
    manifest_path = ROOT / "app/handoff/v2-validation-2026-10-04/inputs/manifest.json"
    manifest = read_json(manifest_path)
    assert manifest["git_commit"] == COMMIT and manifest["branch"] == "nwp-features"
    for item in manifest["files"].values():
        path = ROOT / item["local"]
        assert sha(path) == item["sha256"] and path.stat().st_size == item["bytes"]

    incoming_path = ROOT / manifest["files"]["eval/cv_predictions_v2.csv"]["local"]
    incoming = read_csv(incoming_path)
    original = read_csv(ROOT / "eval/cv_predictions.csv")
    classifier_path = ROOT / "app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv"
    classifier = read_csv(classifier_path)
    assert len(incoming) == len(original) == len(classifier) == selection["validation_hours"] == 3566
    origins = [datetime.fromisoformat(row["time"]) for row in incoming]
    assert origins == sorted(set(origins))
    assert all(value.tzinfo is None for value in origins)
    assert all(b - a == timedelta(hours=1) for a, b in zip(origins, origins[1:]))
    targets = [value + timedelta(hours=24) for value in origins]
    old = {datetime.fromisoformat(row["time"]): row for row in original}
    bits = {datetime.fromisoformat(row["target_time"]): row for row in classifier}
    assert len(old) == len(original) and set(old) == set(origins)
    assert len(bits) == len(classifier) and set(bits) == set(targets)
    for origin, target, row in zip(origins, targets, incoming):
        assert Decimal(row["actual"]) == Decimal(old[origin]["actual"]) == Decimal(bits[target]["weather_actual_w_m2"])
        assert Decimal(row["baseline"]) == Decimal(old[origin]["baseline"])
        assert datetime.fromisoformat(bits[target]["feature_time"]) == origin
        assert bits[target]["predicted_positive"] in ("0", "1")
    identity = selection["incoming"]
    assert identity["sha256"] == sha(incoming_path) and identity["bytes"] == incoming_path.stat().st_size
    assert identity["rows"] == len(incoming) and identity["timestamp_basis"] == "feature"
    assert str(targets[0]) == selection["target_start"] == identity["target_start"]
    assert str(targets[-1]) == selection["target_end"] == identity["target_end"]

    actual = [Decimal(row["actual"]) for row in incoming]
    predicted = [Decimal(row["predicted"]) for row in incoming]
    assert all(value.is_finite() for value in actual + predicted)
    truth = [value > 600 for value in actual]
    errors = [Fraction(prediction) - Fraction(observation) for observation, prediction in zip(actual, predicted)]
    mae = float(sum(abs(value) for value in errors) / len(errors))
    regression = dict(mae_w_m2=mae,
                      rmse_w_m2=math.sqrt(float(sum(value * value for value in errors) / len(errors))),
                      bias_w_m2=float(sum(errors) / len(errors)))
    for key, value in regression.items():
        close(selection["regression_unchanged"][key], value)
    table = read_csv(HERE / "validation-table.csv")
    assert [int(row["threshold_w_m2"]) for row in table] == list(range(500, 651))
    assert selection["grid"] == dict(start=500, stop=650, step=1, candidates=151)
    reconstructed = []
    for row in table:
        threshold = int(row["threshold_w_m2"])
        expected = dict(threshold_w_m2=threshold, **count(truth, [value > threshold for value in predicted]))
        verify_metrics(row, expected)
        close(row["mae_w_m2_unchanged"], mae)
        reconstructed.append(expected)
    best = max(reconstructed, key=lambda row: (Fraction(row["f1_exact"]),
                                               -abs(row["threshold_w_m2"] - 600), row["threshold_w_m2"]))
    original600 = next(row for row in reconstructed if row["threshold_w_m2"] == 600)
    frozen008 = count(truth, [bits[target]["predicted_positive"] == "1" for target in targets])
    for saved, expected in ((selection["selected"], best), (selection["original_threshold"], original600),
                            (selection["frozen_classifier"], frozen008)):
        verify_metrics(saved, expected)
        if "threshold_w_m2" in expected:
            assert saved["threshold_w_m2"] == expected["threshold_w_m2"]
            close(saved["mae_w_m2_unchanged"], mae)
    assert best["threshold_w_m2"] == 562
    assert [best[key] for key in ("tp", "fp", "fn", "tn")] == [287, 51, 19, 3209]
    assert [original600[key] for key in ("tp", "fp", "fn", "tn")] == [262, 25, 44, 3235]
    assert [frozen008[key] for key in ("tp", "fp", "fn", "tn")] == [271, 21, 35, 3239]
    delta = Fraction(best["f1_exact"]) - Fraction(frozen008["f1_exact"])
    assert delta == Fraction(-9, 598) == Fraction(selection["comparison_with_008"]["v2_minus_classifier_f1_exact"])
    close(selection["comparison_with_008"]["v2_minus_classifier_f1"], delta)
    evidence = [protocol, HERE / "validation-table.csv", HERE / "validation-selection.json",
                HERE / "run-receipt.json", HERE / "fixtures.log", HERE / "validation-scan.log", manifest_path]
    source_hashes = dict(pins)
    source_hashes.update({str(path.relative_to(ROOT)): sha(path) for path in evidence})
    source_hashes.update({item["local"]: item["sha256"] for item in manifest["files"].values()})
    return dict(status="PASS", audit="Independent reconstruction of completed validation scan only",
        review_source_sha256=sha(Path(__file__)), input_sha256=source_hashes,
        validation_hours=len(incoming), grid_rows_verified=len(reconstructed),
        target_first=str(targets[0]), target_last=str(targets[-1]),
        selected_v2=best, original_v2_600=original600, frozen008=frozen008,
        regression_unchanged=regression,
        v2_selected_minus_008_f1_exact=str(delta), v2_selected_minus_008_f1=float(delta),
        selected_v2_minus_008_counts={key: best[key] - frozen008[key] for key in ("tp", "fp", "fn", "tn")},
        conclusion="008 has higher F1 and precision on the same reused validation hours. Tuned v2 has higher recall, gaining 16 true positives while adding 30 false positives. This is a validation tradeoff, not evidence that one model is best on unseen data.",
        test_file_metadata=dict(commit=COMMIT,
            command=["git", "ls-tree", "-r", "--name-only", COMMIT, "--", "eval"],
            exit_code=0, retained_stdout=EVAL_TREE,
            stdout_sha256=hashlib.sha256(EVAL_TREE.encode()).hexdigest(),
            interpretation="Local Git tree inspection found no v2 test CSV under eval. The original test_predictions.csv is present. No test file contents were read. This retained metadata inspection is not rerun by --check."),
        limits=["Both 008 and the v2 threshold use validation selection. V2 also used this validation set for early stopping.",
                "No new grid, policy, fitted model, test metric or demo selection was introduced.",
                "The radiation predictions and their regression errors are unchanged by an event threshold."],
        reproduce="python3 app/handoff/v2-calibration-2026-10-04/review.py --check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = inspect()
    path = HERE / "review.json"
    if args.write:
        with path.open("x") as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(path)
    elif args.check:
        assert read_json(path) == result, "Saved review differs"
        print(json.dumps(dict(status="PASS", grid_rows_verified=result["grid_rows_verified"],
                              validation_hours=result["validation_hours"], review_sha256=sha(path))))
    else:
        print(json.dumps(result, indent=2, allow_nan=False))
