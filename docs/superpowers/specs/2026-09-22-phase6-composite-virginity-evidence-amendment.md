# Phase 6 Composite Virginity Evidence Amendment

Status: **FROZEN PRE-ACCESS**

Date: 2026-09-22

Authority: **INDEPENDENT_AUDIT**

## Context

The replacement holdout is frozen as:

- FQAL
- FDMO
- CSB
- FTXO
- VNLA

No historical market-data request has been made for these symbols by the Phase 6
replacement selector or audit tooling.

The earlier attestation model required complete provider-side query history.
Moomoo OpenD exposes `get_history_kl_quota(get_detail=True)`
(`Qot_RequestHistoryKLQuota`, protocol 3104), which reports detailed
historical-candlestick usage for the current quota period. Moomoo documents the
historical-candlestick quota as a seven-day period and automatically releases
consumed quota after seven days.

Therefore protocol 3104 is provider-side evidence, but it is not complete
lifetime query history.

## Frozen composite evidence rule

Independent Audit may authorize first replacement-holdout historical acquisition
only when both components are clear:

1. **Provider component**
   - Call only `get_history_kl_quota(get_detail=True)`.
   - Protocol 3104.
   - No locked replacement symbol may appear in the returned detailed current-
     period usage list.
   - The exact returned details are canonically hashed.

2. **Retained local-log component**
   - Hash every supplied retained OpenD log file.
   - Scan explicit `Qot_RequestHistoryKL` / protocol-3103 context.
   - Match both `US.<ticker>` and exact bare-ticker forms.
   - No locked replacement symbol may appear in historical-kline context.
   - Raw historical values are never emitted or inspected.

If either component reports a locked symbol, acquisition authorization is
forbidden and Phase 6 remains `UNKNOWN / ABSTAIN`.

## Limitations

The attestation must state both limitations exactly:

- `PROVIDER_QUOTA_HISTORY_LIMITED_TO_CURRENT_7_DAY_PERIOD`
- `RETAINED_LOCAL_LOGS_NOT_PROVIDER_IMMUTABLE`

It must also state `complete_query_history=false`.

The composite evidence therefore does not claim a lifetime provider-side audit
trail or decision-grade holdout virginity. It is accepted only for the already
declared Phase 6 non-decision-grade research-comparability exercise.

## Why this is not result-dependent relaxation

This amendment is frozen before any historical market data for the replacement
holdout is requested or evaluated.

It changes only the evidence standard used to determine whether first access may
occur, because the provider's documented history-ledger capability is limited
to the current seven-day quota period.

It does not change:

- replacement symbols;
- ranking or selection seed;
- candidate;
- strategy parameters;
- evaluation window;
- methodology;
- friction;
- execution timing;
- performance metrics;
- one-time consumption semantics;
- Phase 5 status;
- Phase 7 prohibition;
- production-readiness prohibition.

## Moomoo documentation

- Get Details of Historical Candlestick Quota:
  https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-history-kl-quota.html
- Authorities and Quota:
  https://openapi.moomoo.com/moomoo-api-doc/en/intro/authority.html
- Get Historical Candlesticks:
  https://openapi.moomoo.com/moomoo-api-doc/en/quote/request-history-kline.html
