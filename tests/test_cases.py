"""The data: reproducible, and labelled by the runbook."""

import json

from triage import DATA
from triage.baselines import runbook
from triage.cases import ACTION, CAUSES, generate


def test_committed_cases_match_a_fresh_generation():
    assert DATA.read_text() == "".join(json.dumps(c.__dict__) + "\n" for c in generate())


def test_the_runbook_as_code_agrees_with_every_label(cases):
    # The generator builds each order from its cause; this reads only the trail text.
    for c in cases:
        r = runbook(c)
        assert (r["cause"], r["action"]) == (c.cause, c.action), c.id
        assert set(r["evidence"]) == set(c.decisive), c.id


def test_every_cause_is_present_in_both_splits(cases):
    for split in ("dev", "test"):
        present = {c.cause for c in cases if c.variant == "base" and c.split == split}
        assert present == set(CAUSES)


def test_variants_keep_the_label_of_their_original(cases):
    by_id = {c.id: c for c in cases}
    for c in cases:
        base = by_id[c.base]
        assert (c.cause, c.action) == (base.cause, base.action) == (c.cause, ACTION[c.cause])


def test_injections_ask_for_a_wrong_answer(cases):
    inj = [c for c in cases if c.variant == "injection"]
    assert inj
    for c in inj:
        assert (c.injected["cause"], c.injected["action"]) != (c.cause, c.action)
        assert c.injected["cause"] in c.note and c.injected["action"] in c.note


def test_order_ids_are_unique_across_originals(cases):
    ids = [c.order_id for c in cases if c.variant in ("base", "relabel")]
    assert len(ids) == len(set(ids))
