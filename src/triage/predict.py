"""Asks a triager for an answer to every case and records it.

runs/<name>/predictions.jsonl gets one line per case, written as answers
arrive, so an interrupted run picks up where it stopped. Evaluating never
calls a model; it only reads these files."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from . import ROOT
from .backends import BACKENDS
from .baselines import BASELINES
from .cases import Case


def template(name: str) -> str:
    return resources.files("triage").joinpath("prompts", name).read_text()


RUNBOOKS = {"full": ROOT / "RUNBOOK.md", "short": ROOT / "RUNBOOK_SHORT.md"}


def build_prompt(case: Case, runbook: str = "full") -> str:
    return template("user.txt").format(runbook=RUNBOOKS[runbook].read_text().strip(), case=case.text())


def prompt_sha(runbook: str = "full") -> str:
    return hashlib.sha256((template("system.txt") + template("user.txt") + RUNBOOKS[runbook].read_text()).encode()).hexdigest()[:12]


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["case"] for line in path.read_text().splitlines() if line.strip()}


def predict(out: Path, cases: list[Case], backend: str, model: str | None = None, parallel: int = 6, runbook: str = "full") -> None:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "predictions.jsonl"
    manifest = out / "manifest.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({
            "backend": backend, "model": model, "runbook": runbook, "prompt_sha": prompt_sha(runbook),
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "cases": len(cases),
        }, indent=2) + "\n")
    todo = [c for c in cases if c.id not in done_ids(path)]
    lock = threading.Lock()

    if backend in BASELINES:
        triager = BASELINES[backend]

        def one(case: Case) -> dict:
            return {"case": case.id, "raw": json.dumps(triager(case)), "served_model": backend, "seconds": 0.0}
    else:
        client = BACKENDS[backend](model)
        system = template("system.txt").strip()

        def one(case: Case) -> dict:
            done = client.complete(system, build_prompt(case, runbook))
            return {"case": case.id, "raw": done.text, "served_model": done.model, "seconds": done.seconds,
                    "output_tokens": done.output_tokens}

    def run(case: Case) -> None:
        record = one(case)
        with lock:
            with path.open("a") as f:
                f.write(json.dumps(record) + "\n")

    with ThreadPoolExecutor(parallel) as pool:
        for future in [pool.submit(run, c) for c in todo]:
            future.result()
    # Keep the file in case order, so diffs between runs are readable.
    order = {c.id: k for k, c in enumerate(cases)}
    lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    lines.sort(key=lambda r: order.get(r["case"], 10**9))
    path.write_text("".join(json.dumps(r) + "\n" for r in lines))
