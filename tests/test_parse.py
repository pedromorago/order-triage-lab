from triage.evaluate import parse

GOOD = '{"order_id": "ORD-1", "cause": "payment_timeout", "action": "retry", "confidence": 0.8, "evidence": ["E04"]}'


def test_reads_an_answer_in_a_code_fence():
    data, err = parse("```json\n" + GOOD + "\n```")
    assert err is None and data["cause"] == "payment_timeout"


def test_rejects_answers_outside_the_runbook():
    for bad, reason in [
        ("no json here", "no JSON"),
        (GOOD.replace("payment_timeout", "network_blip"), "unknown cause"),
        (GOOD.replace('"retry"', '"refund"'), "unknown action"),
        (GOOD.replace("0.8", "80"), "probability"),
        (GOOD.replace("0.8", "true"), "probability"),
        (GOOD.replace('["E04"]', "[]"), "evidence"),
        ('{"cause": "unknown", ', "no JSON"),
    ]:
        data, err = parse(bad)
        assert data is None and reason in err, bad
