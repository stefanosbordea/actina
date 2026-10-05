"""Capture historical prediction/observation streams, with validation observations separated."""
import csv
from datetime import datetime, timedelta, timezone
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
    sources = {}
    def read(path):
        content = path.read_bytes()
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(content).hexdigest()
        return content
    def rows(path):
        return list(csv.DictReader(io.StringIO(read(path).decode())))
    training = rows(ROOT / "app/experiments/v2-017/inputs/train.csv")
    validation = rows(ROOT / "app/experiments/v2-017/inputs/validation.csv")
    oof = rows(ROOT / "app/experiments/v2-016/result/base-oof.csv")
    first = datetime.fromisoformat(training[0]["origin"]) - timedelta(days=14)
    split = datetime.fromisoformat(training[-1]["origin"])
    stop = datetime.fromisoformat(validation[-1]["origin"])
    weather_bytes = subprocess.check_output(["git", "show", f"{COMMIT}:data/paphos_weather_datav2.csv"], cwd=ROOT)
    weather_sha = hashlib.sha256(weather_bytes).hexdigest()
    weather = {datetime.fromisoformat(row["time"]): float(row["shortwave_radiation"])
        for row in csv.DictReader(io.StringIO(weather_bytes.decode()))
        if first <= datetime.fromisoformat(row["time"]) < stop}
    old_archive = json.loads(read(ROOT / "app/experiments/nwp-archive-001/archive.json"))["hourly"]
    ec = {datetime.fromtimestamp(epoch, timezone(timedelta(hours=3))).replace(tzinfo=None): value
          for epoch, value in zip(old_archive["time"], old_archive["shortwave_radiation_previous_day2"])}
    base = {}
    for row in oof + validation:
        origin = datetime.fromisoformat(row["origin"])
        target = origin + timedelta(hours=24)
        assert target not in base
        base[target] = (origin, float(row["base_prediction"]))
    for row in training:
        target = datetime.fromisoformat(row["target_time"])
        if target in weather:
            assert weather[target] == float(row["target"])
    records = []
    for target in sorted(weather):
        prior = base.get(target)
        records.append(dict(target_time=str(target), v2_source_origin=str(prior[0]) if prior else "",
            v2_prediction=prior[1] if prior else "", ecmwf_prediction=ec.get(target, "")))
    def write(name, records):
        with (out / name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    write("history-predictions.csv", records)
    write("observations-training.csv", [dict(target_time=str(t), actual=weather[t]) for t in sorted(weather) if t < split])
    write("observations-validation-stream.csv", [dict(target_time=str(t), actual=weather[t]) for t in sorted(weather) if t >= split])
    manifest = dict(source_sha256=sources, upstream_commit=COMMIT,
        upstream_weather_sha256=weather_sha, upstream_weather_file="data/paphos_weather_datav2.csv",
        files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())},
        earliest_observation=str(first), validation_observation_stream_start=str(split),
        observation_end_exclusive=str(stop),
        scope="Only observations before the final validation decision origin are retained. No test-period observations or metrics. Source v2 forecast origin is retained for every available prediction.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(status="PASS", observation_hours=len(weather), first=str(first), end_exclusive=str(stop))))


if __name__ == "__main__":
    main()
