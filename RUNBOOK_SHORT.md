# Failed order triage runbook (short)

An order that can't be completed lands in the failed-orders queue with its event trail. Decide why it failed (the cause) and what happens next (the action).

| Cause | Signature | Action |
|---|---|---|
| `fraud_review` | `risk.score` hold | `manual_review` |
| `duplicate_order` | `checkout.dedupe` match | `cancel_refund` |
| `price_mismatch` | `checkout.validate` price changed | `manual_review` |
| `payment_declined` | `payment.authorize` declined | `contact_customer` |
| `payment_timeout` | `payment.authorize` timed out | `retry` |
| `out_of_stock` | `inventory.reserve` insufficient | `contact_customer` |
| `invalid_address` | `carrier.label` rejected for the address | `contact_customer` |
| `carrier_outage` | `carrier.label` error from the carrier | `retry` |
| `unknown` | Anything else | `manual_review` |

The cause is the failure that stopped the order.

Reply with one JSON object and nothing else:

```json
{"order_id": "ORD-48213", "cause": "payment_timeout", "action": "retry", "confidence": 0.9, "evidence": ["E07"]}
```

- `order_id`: the order's id, from the trail.
- `cause` and `action`: values from the table.
- `confidence`: your probability, from 0 to 1, that the cause is right.
- `evidence`: the ids of the events that show the cause, at least one.
