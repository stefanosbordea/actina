"""Verify upstream row shifts from retained local Git objects, without fitting."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = "85097a560769ad8a1459ce55f0b3a4c301202405"


def main():
    identities = {}
    def source(name):
        blob = subprocess.check_output(["git", "show", f"{COMMIT}:{name}"], cwd=ROOT)
        identities[name] = hashlib.sha256(blob).hexdigest()
        rows = list(csv.DictReader(io.StringIO(blob.decode())))
        table = {datetime.fromisoformat(row["time"]): row for row in rows}
        assert len(table) == len(rows)
        return table
    weather = source("data/paphos_weather_datav2.csv")
    nwp = source("data/paphos_nwp_data.csv")
    features = source("data/featuresv2.csv")
    union = sorted(set(weather) | set(nwp))
    positions = {value: number for number, value in enumerate(union)}
    grids = {}
    for name, table in (("weather", weather), ("nwp", nwp), ("union", dict.fromkeys(union))):
        times = sorted(table)
        gaps = [(str(a), str(b)) for a, b in zip(times, times[1:]) if b - a != timedelta(hours=1)]
        grids[name] = dict(rows=len(times), first=str(times[0]), last=str(times[-1]), non_hourly_gaps=gaps)
    assert not any(item["non_hourly_gaps"] for item in grids.values())
    summaries = {}
    for name, first, last in (("train", "2024-01-18 15:00", "2025-12-03 18:00"),
                              ("validation", "2025-12-04 19:00", "2026-05-02 08:00")):
        times = [value for value in sorted(features) if datetime.fromisoformat(first) <= value <= datetime.fromisoformat(last)]
        misaligned, lag_misaligned = [], []
        for origin in times:
            target = union[positions[origin] + 24]
            past = union[positions[origin] - 24]
            if target != origin + timedelta(hours=24):
                misaligned.append(str(origin))
            if past != origin - timedelta(hours=24):
                lag_misaligned.append(str(origin))
            row = features[origin]
            assert Decimal(row["nwp_radiation"]) == Decimal(nwp[target]["nwp_radiation"])
            assert Decimal(row["nwp_cloud"]) == Decimal(nwp[target]["nwp_cloud"])
            assert Decimal(row["radiation_yesterday"]) == Decimal(weather[past]["shortwave_radiation"])
            if name == "train":
                assert Decimal(row["target"]) == Decimal(weather[target]["shortwave_radiation"])
        assert not misaligned and not lag_misaligned
        assert all(b - a == timedelta(hours=1) for a, b in zip(times, times[1:]))
        summaries[name] = dict(rows=len(times), first=str(times[0]), last=str(times[-1]),
            target_shift_not_24h=misaligned, lag_shift_not_24h=lag_misaligned,
            training_rows_excluded=0, both_nwp_values_match_shifted_raw=True,
            past_radiation_matches_raw=True, target_values_checked=(name == "train"))
    assert summaries["train"]["rows"] == 16444 and summaries["validation"]["rows"] == 3566
    result = dict(status="PASS", commit=COMMIT, source_sha256=identities,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), raw_grids=grids, splits=summaries,
        note="Source union grids are hourly. All retained train and validation row shifts equal 24 physical clock hours. No rows need alignment exclusion. Validation target values and all test metrics were not used.")
    with (HERE / "inputs/source-audit.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
