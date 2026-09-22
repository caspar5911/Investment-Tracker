# Generation 2 Holdout Selection — Pre-Query Hash Correction

Date: 2026-09-22

Authority: **INDEPENDENT_AUDIT**

## Status

**CORRECTED BEFORE FIRST CANDIDATE-UNIVERSE QUERY**

The first local invocation of the Generation-2 blind selector terminated with:

`GEN2_HOLDOUT_SELECTION_REGISTRY_MISMATCH`

The call stack shows the failure occurred inside
`_verify_frozen_inputs()`, before `_load_sdk()` and before
`OpenQuoteContext` is created.

Therefore:

- no OpenD context was opened;
- `get_stock_basicinfo` was not called;
- `get_history_kl_quota` was not called;
- no candidate universe was observed;
- no selected symbol or rank key was produced;
- no output snapshot/evidence was written by the selector;
- no historical market data was accessed;
- the selection was not consumed.

## Root cause

The preregistered contract contained an incorrectly calculated
holdout-exclusion-registry SHA-256.

Incorrect value:

`1c7965d2b6250aab9f521dd2c9605e5beb277785a08f846c3ba35447b4e16651`

The authoritative registry identity is defined by
`registry_content_sha256()`, which canonicalizes the validated Pydantic model
as sorted compact JSON.

Correct value:

`de8abace734cd6b1550d68d79166c806203435e1e7f7b48a236f497c32b9bf61`

Because the deterministic selection seed includes the registry identity, the
seed was recomputed before any provider/candidate-universe query.

Prior seed:

`bc41de35fd0b4889a98d06b614e353696a29c539d9398f1d19b2bb7df0094094`

Corrected seed:

`51bc792c6550a3b49e608acf12343153223d29325cbbad97fbbf4785a61a348c`

## Governance interpretation

This is a pre-query identity correction, not a result-dependent seed change.

No eligible symbols, selected symbols, price/history observations, or ranking
results were available when the correction was made.

The strategy survivor, implementation identity, binding identity, evaluation
window, warmup, eligibility rules, exclusion registry contents, selection count,
and no-manual-substitution rule are unchanged.

The corrected contract remains status:

`FROZEN_BEFORE_CANDIDATE_UNIVERSE_QUERY`
