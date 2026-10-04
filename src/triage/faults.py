"""Seeded bugs in the evaluator itself.

Each one is a mistake that is easy to make when scoring a classifier, and
most of them make the triager look better than it is. Setting
TRIAGE_FAULT=<name> switches one on; scripts/run_seeded_bugs.py checks that
the lab's own tests catch every one."""

from __future__ import annotations

import os

FAULTS = {
    "confusion-transposed": "precision and recall are computed from the transposed confusion matrix",
    "invalid-as-abstain": "answers that can't be read are left out instead of counted as wrong",
    "macro-as-micro": "the macro F1 is really the accuracy, so rare causes stop mattering",
    "ece-drops-top-bin": "answers with confidence 1.0 are left out of the calibration error",
    "threshold-on-test": "the auto-handling threshold is chosen on the test cases it is then measured on",
    "evidence-not-checked": "cited event ids are not checked against the trail",
    "consistency-vs-label": "variants are compared with the label instead of the answer to the original",
    "injection-vs-label": "any wrong answer on an injection case counts as the injection working",
    "cost-matrix-transposed": "the cost matrix is read with the true and chosen actions swapped",
    "gate-ignores-per-cause": "the gate only looks at overall numbers, not at each cause",
}


def active(name: str) -> bool:
    if name not in FAULTS:
        raise KeyError(name)
    return os.environ.get("TRIAGE_FAULT") == name
