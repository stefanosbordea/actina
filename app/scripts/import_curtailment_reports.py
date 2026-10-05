"""Extract the published EAC report fields, without estimating chart curves."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_page(text, page, source):
    date = re.search(r"Ημερομηνία Περικοπής:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
    times = re.findall(r"\b\d{1,2}:\d{2}\b", text)
    energy = re.findall(r"([\d.]+)\s*MWh", text)
    percent = re.findall(r"([\d.]+)\s*%", text)
    if not date or len(times) not in (2, 4) or len(energy) != 2 or len(percent) != 1:
        raise ValueError(f"Unexpected report layout: {source['id']}, page {page}")
    day = dt.datetime.strptime(date[1], "%d/%m/%Y").date()
    if day.month != source["month"] or day.day != page or day.year != 2026:
        raise ValueError(f"Unexpected source date: {day}, page {page}")
    times = [dt.datetime.strptime(t, "%H:%M").strftime("%H:%M") for t in times]
    end = 1 if len(times) == 2 else 2
    if times[0] >= times[end]:
        raise ValueError(f"Reversed Group 1 window: {day}")
    if end == 2 and times[1] >= times[3]:
        raise ValueError(f"Reversed Group 2 window: {day}")
    reported_day_energy, curtailed = map(float, energy)
    if not reported_day_energy > 0 or not 0 <= curtailed <= reported_day_energy or not 0 <= float(percent[0]) <= 100:
        raise ValueError(f"Invalid reported energy: {day}")
    half_unit = lambda value: .5 * 10 ** (-len(value.partition(".")[2]))
    day_half, cut_half, percent_half = map(half_unit, [*energy, percent[0]])
    lower = 100 * max(0, curtailed - cut_half) / (reported_day_energy + day_half)
    upper = 100 * (curtailed + cut_half) / (reported_day_energy - day_half)
    discrepancy = not (float(percent[0]) + percent_half >= lower and float(percent[0]) - percent_half <= upper)
    return {
        "date": day.isoformat(),
        "windows": [{"start_local": times[0], "end_local": times[end], "group": 1}],
        "group_2_windows": ([] if end == 1 else [{"start_local": times[1], "end_local": times[3], "group": 2}]),
        "estimated_curtailed_mwh": curtailed,
        "estimated_day_energy_mwh": reported_day_energy,
        "reported_curtailment_percent": float(percent[0]),
        "reported_percent_minus_ratio_pp": round(float(percent[0]) - 100 * curtailed / reported_day_energy, 5),
        "source_ratio_discrepancy": discrepancy,
        "ratio_interval_from_display_precision_percent": [lower, upper],
        "reason": "Low electrical-system load",
        "source_id": source["id"], "source_url": source["url"],
        "source_sha256": source["sha256"], "page": page,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "data/grid-reports/originals")
    args = parser.parse_args()
    folder = ROOT / "data/grid-reports"
    sources = json.loads((folder / "eac-report-sources.json").read_text())
    days, receipts = [], []
    for source in sources:
        pdf = args.pdf_dir / source["filename"]
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Source bytes differ from inspected report: {pdf}")
        # The right-hand report column contains separate Ripple/IoT energy.
        # Crop the actual PDF's left table to preserve the main fields distinctly.
        command = ["pdftotext", "-r", "72", "-x", "0", "-y", "100", "-W", "250", "-H", "345", "-layout", str(pdf), "-"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        name = f"eac-extracted-fields-2026-{source['month']:02d}.txt"
        (folder / name).write_text(result.stdout)
        pages = [p for p in result.stdout.split("\f") if p.strip()]
        if len(pages) != 31:
            raise ValueError(f"Expected 31 daily report pages: {pdf}")
        days.extend(parse_page(text, page, source) for page, text in enumerate(pages, 1))
        receipts.append({"source_id": source["id"], "sha256": digest, "pages": len(pages), "extract": str((folder / name).relative_to(ROOT)), "exit_code": result.returncode})
    if len({d["date"] for d in days}) != len(days):
        raise ValueError("Duplicate report dates")
    payload = {
        "kind": "reported_estimate", "aggregation": "day", "units": "MWh",
        "scope": "Cyprus distribution PV — reported Group 1 curtailment window",
        "energy_scope": "EAC report main estimated curtailed energy; separate Ripple/IoT fields excluded",
        "time_zone_assumption": "Reported times interpreted as Cyprus civil time (Europe/Nicosia), subject to operator confirmation",
        "limitations": "Historical national/grid context, not a Paphos plant allocation or an hourly available-energy series. Missing later reports mean unknown, not zero. No plant recovered energy is measured.",
        "days": days,
    }
    (ROOT / "data/eac_curtailment_days.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with (ROOT / "data/eac_curtailment_days.csv").open("w", newline="") as handle:
        fields = ["date", "group_1_start_local", "group_1_end_local", "estimated_curtailed_mwh", "estimated_day_energy_mwh", "reported_curtailment_percent", "reported_percent_minus_ratio_pp", "source_ratio_discrepancy", "source_id", "page"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for day in days:
            writer.writerow({**{k: day[k] for k in fields if k in day}, "group_1_start_local": day["windows"][0]["start_local"], "group_1_end_local": day["windows"][0]["end_local"]})
    record = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "sources": receipts, "days": len(days), "source_ratio_discrepancies": [d["date"] for d in days if d["source_ratio_discrepancy"]], "status": "executed; source arithmetic discrepancies retained without correction"}
    (ROOT / "results/curtailment-source-import.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
