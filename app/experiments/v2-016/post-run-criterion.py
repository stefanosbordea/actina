"""Apply the user's later reporting criterion without selecting another policy."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "result/summary.json"


def evaluate():
    metrics = json.loads(SOURCE.read_text())["metrics"]
    baseline = metrics["fixed008"]
    return dict(kind="Post-run user criterion, not a frozen selection rule",
        rule="Strictly higher validation F1 than fixed008 and no additional false positives, with precision and recall reported.",
        summary_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        results={arm: dict(passes=Fraction(metrics[arm]["f1_exact"]) > Fraction(baseline["f1_exact"])
                                  and metrics[arm]["fp"] <= baseline["fp"],
                    delta_tp=metrics[arm]["tp"] - baseline["tp"],
                    delta_fp=metrics[arm]["fp"] - baseline["fp"],
                    delta_f1_exact=str(Fraction(metrics[arm]["f1_exact"]) - Fraction(baseline["f1_exact"])),
                    precision=metrics[arm]["precision"], recall=metrics[arm]["recall"])
                 for arm in ("logistic", "boosted")},
        action="Neither head qualifies. No threshold change, new fit or model promotion.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    path = HERE / "post-run-criterion.json"
    if args.write:
        with path.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    elif args.check:
        assert json.loads(path.read_text()) == result
        print("PASS")
    else:
        print(json.dumps(result, indent=2))
