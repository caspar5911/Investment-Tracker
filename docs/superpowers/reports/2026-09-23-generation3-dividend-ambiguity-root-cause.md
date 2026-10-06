# Generation-3 Phase-6 dividend ambiguity — code-only root-cause report

Status: **TECHNICAL ROOT CAUSE IDENTIFIED / SUCCESSOR PROPOSAL NOT AUTHORIZED**

Predecessor closure:
- commit: `df9a0c974a392f414dc9b44551b544aa64e8e7f6`
- result: `PHASE6_UNKNOWN_ABSTAIN`
- terminal reason: `ValueError:SUCCESSOR_PHASE6_DIVIDEND_AMOUNT_AMBIGUOUS`
- holdout consumed: true
- retry: forbidden
- Phase 7: unauthorized
- RECON-009: OPEN

## Scope limitation

No Generation-3 protected-history record, dividend statement, price, return, corporate-action payload, or performance result was inspected to develop this proposal.

The diagnosis uses only:
1. the committed terminal failure reason;
2. the frozen evaluator source;
3. public Moomoo/OpenD documentation and the official open-source Python SDK;
4. synthetic fixtures.

Therefore this report does **not** assert which specific protected record caused the failure.

## Frozen evaluator defect

The Generation-3 evaluator contained `_statement_amount(statement)`.

That function:
1. treats the endpoint `statement` string as a numeric amount source;
2. extracts numeric dividend-looking values from free text;
3. deduplicates extracted values;
4. requires exactly one unique numeric value;
5. raises `SUCCESSOR_PHASE6_DIVIDEND_AMOUNT_AMBIGUOUS` otherwise.

This assumes every decision-relevant distribution-plan string is safely reducible to one numeric dividend amount.

The provider contract does not establish that assumption.

## Provider semantics

The corporate-actions dividend endpoint documents `statement` as a **distribution plan description**, not as a structured numeric amount field. The same endpoint provides structured event metadata such as ex-date and dividend payable date.

OpenD Rehab separately models corporate-action amounts:
- ordinary cash dividend: protocol `dividend`;
- special dividend: protocol `spDividend`.

The official Python SDK maps these to:
- `per_cash_div = rehab.dividend`;
- `special_dividend = rehab.spDividend`.

This mapping is present in official repository `MoomooOpen/py-moomoo-api`, source commit `dfb09498bdd34bdeb37c12b3cfec6d55908450d9`.

## Proposed successor rule

Numeric dividend amount authority becomes the structured Rehab fields.

The corporate-actions dividend endpoint remains required and is used for:
- event existence corroboration;
- ex-date reconciliation;
- pay-date authority;
- immutable source-record identity;
- non-empty distribution-plan evidence.

The endpoint `statement` is **not parsed numerically**.

Ordinary and special dividend ledger events remain distinct structured components.

## Fail-closed behavior

The successor fails closed for:
- missing decision-relevant Rehab amount evidence;
- negative or non-finite structured amounts;
- zero total cash amount for a cash event;
- missing endpoint event;
- blank endpoint statement;
- duplicate endpoint source identity;
- ambiguous pay date;
- pay date before ex-date;
- unsupported corporate action;
- source-date disagreement.

## Code isolation

Generation-3 frozen files are not modified.

New versioned paths:
- `src/investment_tracker/quant/successor/dividend_reconciliation_v3.py`
- `src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py`

Synthetic tests:
- `tests/quant/test_successor_dividend_reconciliation_v3.py`
- `tests/independent_audit/test_successor_dividend_evaluator_v3.py`

The consumed Generation-3 holdout identities were added to the permanent exclusion registry.

## Governance consequence

Generation 3 cannot be retried.

A future successor requires:
1. Independent Audit approval of this methodology;
2. a formally named successor generation;
3. a new virgin holdout selected without protected-history access;
4. a new one-time acquisition/evaluation authorization;
5. terminal Phase-6 completion before any Phase-7 entry review.

No Phase-7, production-readiness, RECON-009 closure, or live-trading authority is requested.

## Public evidence

- Moomoo corporate-action dividend endpoint:
  https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-corporate-actions-dividends.html
- Moomoo Rehab documentation:
  https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-rehab.html
- Moomoo Rehab protocol / corporate-action definitions:
  https://openapi.moomoo.com/moomoo-api-doc/en/quote/quote.html
- Official Python SDK mapping:
  https://github.com/MoomooOpen/py-moomoo-api/blob/dfb09498bdd34bdeb37c12b3cfec6d55908450d9/moomoo/quote/quote_query.py
