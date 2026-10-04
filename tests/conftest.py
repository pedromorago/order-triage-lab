import json

import pytest

from triage import DATA
from triage.baselines import runbook
from triage.cases import load


@pytest.fixture(scope="session")
def cases():
    return load(DATA)


@pytest.fixture
def perfect(cases):
    """Answers that follow the runbook exactly, as raw model output."""
    return {c.id: json.dumps(runbook(c)) for c in cases}


def answer(case, cause, action, confidence=0.9, evidence=None, order_id=None):
    return json.dumps({"order_id": order_id or case.order_id, "cause": cause, "action": action,
                       "confidence": confidence, "evidence": evidence or case.decisive})
