from pathlib import Path
import os

ROOT = Path(os.environ.get("TRIAGE_ROOT", Path(__file__).resolve().parents[2]))
DATA = ROOT / "data" / "cases.jsonl"
RUNS = ROOT / "runs"
RUNBOOK = ROOT / "RUNBOOK.md"
