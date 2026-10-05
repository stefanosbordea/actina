"""Capture fixed local source inputs, separating validation features from outcomes."""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = "85097a560769ad8a1459ce55f0b3a4c301202405"


def main():
    out = HERE / "inputs"
    out.mkdir(exist_ok=False)
    identities = {}
    def source(name):
        blob = subprocess.check_output(["git", "show", f"{COMMIT}:{name}"], cwd=ROOT)
        identities[name] = dict(sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))
        return blob
    blob = source("data/featuresv2.csv")
    reader = csv.DictReader(io.StringIO(blob.decode()))
    names = reader.fieldnames
    train, validation = [], []
    for row in reader:
        if row["time"] <= "2025-12-03 18:00:00":
            train.append(row)
        elif "2025-12-04 19:00:00" <= row["time"] <= "2026-05-02 08:00:00":
            validation.append({key: value for key, value in row.items() if key != "target"})
    assert len(train) == 16444 and len(validation) == 3566
    for name, rows, fields in (("train.csv", train, names),
                              ("validation-features.csv", validation, [key for key in names if key != "target"])):
        with (out / name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    for path in ("model/train_modelv2.py", "data/features_v2.py", "data/download_nwp.py", "eval/cv_predictions_v2.csv"):
        (out / Path(path).name).write_bytes(source(path))
    copies = {
        "original-validation.csv": "eval/cv_predictions.csv",
        "fixed008-validation.csv": "app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv",
    }
    for local, original in copies.items():
        content = (ROOT / original).read_bytes()
        (out / local).write_bytes(content)
        identities[original] = dict(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
    feature_path = ROOT / "app/experiments/f1-008/result/features.csv"
    identities[str(feature_path.relative_to(ROOT))] = dict(sha256=hashlib.sha256(feature_path.read_bytes()).hexdigest())
    wanted = {row["time"] for row in validation}
    with feature_path.open(newline="") as stream:
        raw = [{"feature_time": row["feature_time"], "nwp_day2_radiation": row["nwp_day2_radiation"]}
               for row in csv.DictReader(stream) if row["feature_time"] in wanted]
    assert len(raw) == 3566 and {row["feature_time"] for row in raw} == wanted
    with (out / "retained-day2-validation.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["feature_time", "nwp_day2_radiation"])
        writer.writeheader()
        writer.writerows(raw)
    manifest = dict(git_commit=COMMIT, capture="Local git show and existing retained comparator files. No download or training.",
                    original_sources=identities,
                    files={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.iterdir())},
                    train_rows=len(train), validation_rows=len(validation),
                    split="Original v2 cutoff. Validation targets excluded from validation-features.csv. Test rows are not retained.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
