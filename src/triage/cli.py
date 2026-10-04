from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import DATA, ROOT, runs
from .cases import generate, load, save


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="triage", description="Evaluate a failed-order triager.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("cases", help="regenerate data/cases.jsonl")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--check", action="store_true", help="fail if the committed file differs from a fresh generation")

    pr = sub.add_parser("predict", help="record a triager's answers")
    pr.add_argument("out", type=Path)
    pr.add_argument("--backend", required=True, help="claude-code, anthropic-api, or a baseline: runbook, last_error, all_manual")
    pr.add_argument("--model")
    pr.add_argument("--limit", type=int, help="only the first N cases")
    pr.add_argument("--parallel", type=int, default=6)

    e = sub.add_parser("evaluate", help="evaluate recorded runs and write results.json in each")
    e.add_argument("runs", type=Path, nargs="+")

    t = sub.add_parser("report", help="comparison table of evaluated runs")
    t.add_argument("runs", type=Path, nargs="+")

    gt = sub.add_parser("gate", help="fail when a run is below the floors or regresses against a baseline")
    gt.add_argument("candidate", type=Path)
    gt.add_argument("--baseline", type=Path)
    gt.add_argument("--config", type=Path, default=ROOT / "gate.json")

    a = p.parse_args(argv)

    if a.cmd == "cases":
        cases = generate(a.seed)
        if a.check:
            fresh = "".join(json.dumps(c.__dict__) + "\n" for c in cases)
            if DATA.read_text() != fresh:
                print("data/cases.jsonl differs from a fresh generation")
                return 1
            print(f"data/cases.jsonl matches seed {a.seed}: {len(cases)} cases")
            return 0
        DATA.parent.mkdir(exist_ok=True)
        save(cases, DATA)
        print(f"{len(cases)} cases written to {DATA}")
        return 0

    if a.cmd == "predict":
        from .predict import predict

        cases = load(DATA)
        predict(a.out, cases[: a.limit] if a.limit else cases, a.backend, a.model, a.parallel)
        return 0

    if a.cmd == "evaluate":
        for run in a.runs:
            r = runs.evaluate_run(run)
            print(runs.table([r]).splitlines()[-1])
        return 0

    if a.cmd == "report":
        print(runs.table([runs.load_result(r) for r in a.runs]))
        return 0

    if a.cmd == "gate":
        config = json.loads(a.config.read_text())
        problems = runs.gate(runs.load_result(a.candidate), runs.load_result(a.baseline) if a.baseline else None, config)
        for problem in problems:
            print(f"FAIL  {problem}")
        print("gate passed" if not problems else f"gate failed: {len(problems)} problem(s)")
        return 1 if problems else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
