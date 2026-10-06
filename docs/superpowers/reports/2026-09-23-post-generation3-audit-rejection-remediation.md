# Independent Audit rejection remediation — post-Generation-3 successor

Status: **COORDINATOR REMEDIATION COMPLETE / RE-AUDIT REQUIRED**

Rejected review:
- verdict: REJECTED
- reviewed head: `556fd7ecae071cdc714d536e642242a354e488ce`
- proposed formal successor name: `GENERATION_4` (naming decision only; not authorized)
- protected history accessed by auditor: no

## Finding 1 — negative structured Rehab cash was filtered before validation

The rejected evaluator built structured components and then filtered with:

`amount > 0.0`

before invoking the structured reconciliation helper.

Consequences demonstrated by the auditor:
- ordinary = -1, special = 2 could degrade to a valid-looking special-only event;
- ordinary = -1, special = 0 could degrade to no event.

This violated the frozen fail-closed methodology requirement for negative structured amounts.

### Remediation

A dedicated raw structured-component validator now runs **before any positive-only event filtering**:

`validate_structured_dividend_components(...)`

It rejects negative or non-finite ordinary/special values before:
- cash-event detection;
- endpoint reconciliation;
- ledger event construction.

Zero/zero remains valid as "no structured cash component" only when no endpoint cash event exists. If endpoint evidence exists with zero total structured amount, the event reconciliation still fails closed.

Regression coverage includes exactly:
- `ordinary=-1, special=2`;
- `ordinary=-1, special=0`.

Both must raise:
`SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID`.

## Finding 2 — predecessor symbol-substitution invariant was not enforced by authority loader

The authority model already required:
`symbol_substitution_after_access_allowed=false`

for a future authorization artifact.

However, the loader did not verify the immutable predecessor closure field:

`one_time_semantics.symbol_substitution_authorized=false`.

### Remediation

`post_generation3.authority.load_methodology_authorization` now rejects any predecessor closure where:

`symbol_substitution_authorized != false`.

A synthetic tampered predecessor closure with the value changed to true now fails with:

`POST_GEN3_PREDECESSOR_CLOSURE_MISMATCH`.

## Scope

No consumed Generation-3 protected data was accessed or inspected for these fixes.

No strategy, parameters, split methodology, dividend methodology intent, selected symbols, performance thresholds, or Phase-7 rules changed.

This remediation changes only:
- enforcement order for already-required fail-closed structured dividend validation;
- enforcement of an already-required predecessor governance invariant;
- synthetic regression tests.

## Re-audit requirement

The prior rejection remains authoritative for the reviewed head.

A fresh Independent Audit must review the new branch head and issue a new decision. No methodology authorization may be reused from the rejected head.
