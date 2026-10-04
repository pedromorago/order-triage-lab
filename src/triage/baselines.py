"""Triagers that don't use a model.

- runbook: the runbook as code, reading only the trail text. It must agree
  with every label, which checks the generator against the runbook from an
  independent direction.
- last_error: what a quick script would do: take the last line that looks like
  a failure and map it by keyword. No timestamps, no precedence, no retries.
- all_manual: send every order to a person. The cost to beat.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from .cases import ACTION, Case

LINE = re.compile(r"^(E\d+) (\S+) +(\S+) +(\S+) *(.*)$")


def parse_trail(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        m = LINE.match(line)
        if not m:
            continue
        eid, ts, service, step, rest = m.groups()
        fields = dict(kv.split("=", 1) for kv in rest.split() if "=" in kv)
        events.append({"id": eid, "t": datetime.fromisoformat(ts.replace("Z", "+00:00")), "stage": f"{service}.{step}", **fields})
    return sorted(events, key=lambda e: e["t"])


def _signature(e: dict) -> str | None:
    stage, result = e["stage"], e.get("result")
    if stage == "checkout.dedupe" and "match" in e and e["match"] != e.get("order"):
        return "duplicate_order"
    if stage == "checkout.validate" and result == "price_changed":
        return "price_mismatch"
    if stage == "payment.authorize":
        if result == "declined" and e.get("code") in ("05", "51", "54"):
            return "payment_declined"
        if result == "timeout":
            return "payment_timeout"
        if result not in ("approved",):
            return "unknown"
    if stage == "inventory.reserve":
        if result == "insufficient":
            return "out_of_stock"
        if result not in ("reserved",):
            return "transient"
    if stage == "warehouse.pick" and result != "picked":
        return "unknown"
    if stage == "carrier.label" and result != "created":
        if result == "rejected" and e.get("reason", "").startswith("address_"):
            return "invalid_address"
        if result == "error" and e.get("http", "").startswith("5"):
            return "carrier_outage"
        return "unknown"
    return None


def runbook(case: Case) -> dict:
    events = parse_trail(case.trail)
    order_id = next((e["order"] for e in events if e["stage"] == "checkout.submit"), case.order_id)
    events = [e for e in events if e.get("order") in (None, order_id)]  # other orders' events don't count
    holds = [e for e in events if e["stage"] == "risk.score" and e.get("decision") == "hold"]
    released = [e for e in events if e["stage"] == "risk.review" and e.get("decision") == "release"]
    holds = [h for h in holds if not any(r["t"] > h["t"] for r in released)]
    if holds:
        return answer(order_id, "fraud_review", 1.0, [e["id"] for e in holds])
    for k, e in enumerate(events):
        sig = _signature(e)
        if sig is None:
            continue
        resolved = any(
            later["stage"] == e["stage"] and _signature(later) is None and later.get("result") not in (None,)
            for later in events[k + 1:]
        )
        if resolved:
            continue
        if sig == "transient":
            sig = "unknown"
        same = [x["id"] for x in events if x["stage"] == e["stage"] and _signature(x) == sig]
        return answer(order_id, sig, 1.0, same)
    return answer(order_id, "unknown", 0.5, [events[-1]["id"]] if events else [])


KEYWORDS = [
    ("hold", "fraud_review"), ("dedupe", "duplicate_order"), ("price_changed", "price_mismatch"),
    ("declined", "payment_declined"), ("timeout", "payment_timeout"), ("insufficient", "out_of_stock"),
    ("address_", "invalid_address"), ("http=5", "carrier_outage"),
]
FAILURE = re.compile(r"result=(?!ok|approved|reserved|picked|created)|decision=hold|dedupe")


def last_error(case: Case) -> dict:
    failing = [line for line in case.trail if FAILURE.search(line)]
    if not failing:
        return answer(case.order_id, "unknown", 0.5, [])
    line = failing[-1]
    cause = next((c for k, c in KEYWORDS if k in line), "unknown")
    return answer(case.order_id, cause, 0.9, [line.split()[0]])


def all_manual(case: Case) -> dict:
    return answer(case.order_id, "unknown", 1.0, [case.trail[-1].split()[0]])


def answer(order_id: str, cause: str, confidence: float, evidence: list[str]) -> dict:
    return {"order_id": order_id, "cause": cause, "action": ACTION[cause], "confidence": confidence, "evidence": evidence}


BASELINES = {"runbook": runbook, "last_error": last_error, "all_manual": all_manual}


def raw(prediction: dict) -> str:
    return json.dumps(prediction)
