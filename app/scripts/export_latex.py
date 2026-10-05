"""Export the three reviewed LaTeX sources with the installed Tectonic compiler."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Executive-Summary", "Technical-Proposal", "Business-Model-Canvas")
compiler = shutil.which("tectonic")
if not compiler:
    raise SystemExit("Tectonic is needed for command-line PDF export. The native editor can still compile the sources.")
records = []
for name in NAMES:
    source = ROOT / "delivery" / f"AquaShift-{name}.tex"
    command = [compiler, "--outdir", str(source.parent), str(source)]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = ROOT / "build" / "latex-review" / f"{name}-export.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(run.stdout + run.stderr)
    if run.returncode:
        raise SystemExit(f"Compiler exit {run.returncode}: inspect {log}")
    output = source.with_suffix(".pdf")
    records.append({
        "source": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output": str(output.relative_to(ROOT)),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
        "exit_code": run.returncode,
        "command": command,
        "log": str(log.relative_to(ROOT)),
    })
receipt = {
    "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "compiler": subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True).stdout.strip(),
    "documents": records,
    "scope": "Executed PDF export. Native editor diagnostics and rendered visual checks are recorded separately.",
}
(ROOT / "results" / "latex-delivery.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
