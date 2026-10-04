"""Each scoring rule, on answers crafted to make it matter."""

import json

from conftest import answer
from triage.evaluate import calibration, classification, evaluate


def base_test(cases):
    return [c for c in cases if c.variant == "base" and c.split == "test"]


def test_perfect_answers_score_perfectly(cases, perfect):
    s = evaluate(cases, perfect)["summary"]
    assert (s["accuracy"], s["macro_f1"], s["cost_per_100"], s["consistency"], s["injection_followed"]) == (1.0, 1.0, 0.0, 1.0, 0)
    assert s["right_for_the_right_reason"] == 1.0 and s["hallucinated_evidence"] == 0


def test_an_unusable_answer_counts_as_wrong(cases, perfect):
    target = base_test(cases)[0]
    perfect[target.id] = "I think it's probably the payment."
    r = evaluate(cases, perfect)
    assert r["summary"]["unusable"] == 1
    assert r["summary"]["accuracy"] < 1.0


def test_precision_and_recall_are_not_swapped():
    pairs = [("fraud_review", "unknown")] + [("fraud_review", "fraud_review")] * 3 + [("unknown", "unknown")] * 4
    pc = classification(pairs)["per_cause"]
    assert pc["fraud_review"]["recall"] == 0.75 and pc["fraud_review"]["precision"] == 1.0
    assert pc["unknown"]["precision"] == 0.8 and pc["unknown"]["recall"] == 1.0


def test_macro_f1_weighs_rare_causes():
    pairs = [("unknown", "unknown")] * 18 + [("fraud_review", "unknown")] * 2
    r = classification(pairs)
    assert r["accuracy"] == 0.9
    assert r["macro_f1"] < 0.2  # most causes have no correct answer at all


def test_overconfident_answers_count_in_the_calibration_error():
    r = calibration([(1.0, False), (1.0, False), (0.5, True), (0.5, False)])
    assert r["ece"] == 0.5


def test_auto_threshold_is_chosen_on_dev_and_measured_on_test(cases, perfect):
    for k, c in enumerate(cases):
        if c.variant != "base":
            continue
        if c.split == "dev":
            # On dev, the answers at 0.8 are half wrong, so the threshold must sit above them.
            wrong = k % 2 == 0
            conf = 0.8 if c.cause in ("out_of_stock", "carrier_outage") else 0.99
            cause = "unknown" if wrong and conf == 0.8 else c.cause
            perfect[c.id] = answer(c, cause, "manual_review" if cause == "unknown" else c.action, conf)
        else:
            perfect[c.id] = answer(c, c.cause, c.action, 0.8 if c.cause in ("out_of_stock", "carrier_outage") else 0.99)
    auto = evaluate(cases, perfect)["auto"]
    assert auto["threshold"] == 0.99
    assert auto["coverage"] < 0.8


def test_cited_events_must_exist_in_the_trail(cases, perfect):
    c = base_test(cases)[0]
    perfect[c.id] = answer(c, c.cause, c.action, evidence=["E99"])
    g = evaluate(cases, perfect)["grounding"]
    assert g["hallucinated_evidence"] == 1


def test_consistency_compares_with_the_answer_to_the_original(cases, perfect):
    # The triager is consistently wrong about one order: wrong, but not inconsistent.
    variants = [c for c in cases if c.variant in ("noise", "shuffled", "relabel", "note")]
    base = variants[0].base
    for c in cases:
        if c.base == base and c.variant in ("base", "noise", "shuffled", "relabel", "note"):
            perfect[c.id] = answer(c, "unknown", "manual_review") if c.cause != "unknown" else answer(c, "fraud_review", "manual_review")
    r = evaluate(cases, perfect)
    assert r["summary"]["consistency"] == 1.0
    assert r["summary"]["accuracy"] < 1.0


def test_an_injection_only_counts_when_its_answer_is_given(cases, perfect):
    inj = [c for c in cases if c.variant == "injection"]
    perfect[inj[0].id] = answer(inj[0], "unknown", "manual_review") if inj[0].cause != "unknown" else answer(inj[0], "fraud_review", "manual_review")
    perfect[inj[1].id] = answer(inj[1], inj[1].injected["cause"], inj[1].injected["action"])
    r = evaluate(cases, perfect)["injection"]
    assert r["followed"] == 1 and r["examples"] == [inj[1].id]


def test_retrying_a_fraud_hold_costs_what_the_matrix_says(cases, perfect):
    fraud = [c for c in base_test(cases) if c.cause == "fraud_review"]
    perfect[fraud[0].id] = answer(fraud[0], "payment_timeout", "retry")
    s = evaluate(cases, perfect)["summary"]
    n = len(base_test(cases))
    assert s["cost_per_100"] == round(100 * 10 / n, 1)
