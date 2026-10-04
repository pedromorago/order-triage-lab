"""Switches on each seeded bug in the evaluator, one at a time, and runs the
lab's own tests. Every bug must make at least one test fail; with no bug,
everything must pass. Prints a Markdown table of what caught what."""

import os
import re
import subprocess
import sys

from triage.faults import FAULTS


def failing(fault: str | None) -> list[str]:
    env = {**os.environ}
    env.pop("TRIAGE_FAULT", None)
    if fault:
        env["TRIAGE_FAULT"] = fault
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no", "-rf", "-p", "no:cacheprovider"],
        env=env, capture_output=True, text=True,
    )
    return sorted(set(re.findall(r"^FAILED tests/(\S+?)(?:\[|\s|$)", done.stdout, re.M)))


def main() -> int:
    ok = True
    clean = failing(None)
    if clean:
        ok = False
        print("Without seeded bugs these fail: " + ", ".join(clean))
    print("| Seeded bug in the evaluator | Caught by |")
    print("|---|---|")
    for name, what in FAULTS.items():
        caught = failing(name)
        ok &= bool(caught)
        print(f"| `{name}`: {what} | {', '.join(f'`{c}`' for c in caught) or '**nothing**'} |")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
