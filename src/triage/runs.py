"""Evaluating recorded runs, gating one against another, and the comparison table."""

from __future__ import annotations

import json
from pathlib import Path

from . import DATA, faults
from .cases import load
from .evaluate import evaluate


def raws(run: Path) -> dict[str, str]:
    return {r["case"]: r["raw"] for r in map(json.loads, (run / "predictions.jsonl").read_text().splitlines()) if r}


def evaluate_run(run: Path) -> dict:
    result = evaluate(load(DATA), raws(run))
    manifest = json.loads((run / "manifest.json").read_text()) if (run / "manifest.json").exists() else {}
    result = {"run": run.name, "manifest": manifest, **result}
    (run / "results.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return result


def load_result(run: Path) -> dict:
    return json.loads((run / "results.json").read_text())


def gate(candidate: dict, baseline: dict | None, config: dict) -> list[str]:
    """The reasons the candidate fails; an empty list means it passes."""
    s = candidate["summary"]
    problems = []
    for metric, floor in config.get("min", {}).items():
        if s[metric] is None or s[metric] < floor:
            problems.append(f"{metric} is {s[metric]}, below the floor of {floor}")
    for metric, ceiling in config.get("max", {}).items():
        if s[metric] is not None and s[metric] > ceiling:
            problems.append(f"{metric} is {s[metric]}, above the ceiling of {ceiling}")
    if config.get("cheaper_than_all_manual") and s["cost_per_100"] >= s["all_manual_cost_per_100"]:
        problems.append(f"costs {s['cost_per_100']} per 100 orders, no better than sending all to a person ({s['all_manual_cost_per_100']})")
    if baseline is not None:
        b = baseline["summary"]
        for metric, allowed in config.get("max_drop", {}).items():
            drop = b[metric] - s[metric]
            if drop > allowed:
                problems.append(f"{metric} dropped by {drop:.3f} against {baseline['run']} (allowed {allowed})")
        allowed = config.get("max_recall_drop")
        if allowed is not None and not faults.active("gate-ignores-per-cause"):
            for cause, base in baseline["classification"]["per_cause"].items():
                now = candidate["classification"]["per_cause"][cause]["recall"]
                if base["recall"] - now > allowed:
                    problems.append(f"recall for {cause} dropped from {base['recall']:.2f} to {now:.2f}")
    return problems


def table(results: list[dict]) -> str:
    rows = [
        "| Run | Accuracy | Traps | Macro F1 | Cost per 100 | Auto-handled | ECE | Consistency | Injections followed | Hallucinated evidence | Unusable |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["summary"]
        auto = f"{s['auto_coverage']:.0%}" + (f" at {s['auto_accuracy']:.0%}" if s["auto_accuracy"] is not None else "")
        rows.append(
            f"| {r['run']} | {s['accuracy']:.1%} | {s['trap_accuracy']:.0%} | {s['macro_f1']:.3f} | {s['cost_per_100']} (all manual {s['all_manual_cost_per_100']}) "
            f"| {auto} | {s['ece']:.3f} | {s['consistency']:.1%} | {s['injection_followed']} of {r['injection']['cases']} "
            f"| {s['hallucinated_evidence']} | {s['unusable']} |"
        )
    return "\n".join(rows)
