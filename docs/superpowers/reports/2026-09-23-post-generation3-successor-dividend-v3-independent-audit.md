# Post-Generation-3 successor dividend v3 independent audit

Audit decision: **REJECTED**

Audit authority: `INDEPENDENT_AUDIT`

Reviewed branch: `governance/phase6-successor-dividend-normalization-v3`

Reviewed branch head: `556fd7ecae071cdc714d536e642242a354e488ce`

Immutable predecessor: `df9a0c974a392f414dc9b44551b544aa64e8e7f6`

Audit completed at: `2026-09-23T07:37:16Z`

Protected Generation-3 history accessed: **no**

## Decision

The proposed successor methodology is rejected because the integrated successor evaluator does not fail closed on negative structured Rehab cash amounts. A separate governance-gate omission also permits a predecessor closure with symbol substitution authorized. Either condition is inconsistent with the requested authorization boundary.

No `SUCCESSOR-PHASE6-METHODOLOGY-AUTHORIZATION-v2` artifact was issued. New virgin holdout selection, protected-history access, acquisition, Phase 7, production readiness, and live trading remain unauthorized. RECON-009 remains `OPEN`, and the system remains paper-only.

The independent formal-name decision is `GENERATION_4`. This naming decision does not authorize or freeze an evaluation window, pre-window session count, listing cutoff, selection count, or selection seed; those values must be selected only after the blockers are repaired and the replacement commit passes a new Independent Audit.

## Material blockers

### 1. Negative structured cash bypasses the fail-closed validator

The dividend contract requires ordinary and special structured cash values to be nonnegative and finite, and lists `NONFINITE_OR_NEGATIVE_STRUCTURED_AMOUNT` as a fail-closed condition.

The standalone reconciliation helper enforces that rule. The integrated evaluator does not. In `src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py`, `_corporate_actions` first filters the Rehab components to amounts strictly greater than zero and only then calls `reconcile_structured_dividend_amounts`. A negative component is therefore discarded before the validator receives it.

Independent synthetic probes against the reviewed source produced:

```text
ordinary=-1.0, special=2.0, endpoint present  -> ACCEPTED [2.0]
ordinary=-1.0, special=0.0, endpoint absent   -> ACCEPTED []
```

Both cases must fail closed. The first silently drops a negative ordinary component and records only the special component. The second silently treats a negative cash row as no event.

Required repair: validate the raw structured ordinary and special amounts before filtering or event construction, and add evaluator-level regressions for negative ordinary, negative special, non-finite values, and zero-total cash evidence. Do not weaken the standalone reconciliation tests or contract.

### 2. The post-Generation-3 authority gate omits the predecessor symbol-substitution invariant

`src/investment_tracker/independent_audit/post_generation3/authority.py` checks predecessor status, consumption, retry, Phase 7, and RECON-009, but does not require `one_time_semantics.symbol_substitution_authorized` to be false. The reviewed closure currently has the correct false value, but the authority loader would accept a supplied closure with that governance invariant changed.

Required repair: make the loader fail closed unless predecessor symbol substitution is explicitly false, and add a tamper regression. The gate should continue requiring UNKNOWN/ABSTAIN, consumed=true, retry=false, Phase 7=false, and RECON-009 OPEN.

## Verified predecessor closure and immutability

The Generation-3 closure file has the same Git blob at the predecessor and reviewed heads and SHA-256 `b186a23947701d46c59b44627e88bf1a974bdc29bb956bd98b92fbfc923372d9`.

- status: `PHASE6_UNKNOWN_ABSTAIN`
- failure: `ValueError:SUCCESSOR_PHASE6_DIVIDEND_AMOUNT_AMBIGUOUS`
- holdout consumed: true
- retry authorized: false
- symbol substitution authorized: false
- Phase 7 authorized: false
- production readiness approved: false
- RECON-009: `OPEN`

The frozen Generation-3 evaluator is unchanged from the predecessor and has required SHA-256 `c933cc2b71bf068f9db1f4656f7fea57ed3a5e0307819abc177897782e63e0ea`.

## Provider-semantics verification

Independent review of current official documentation and the pinned official SDK source confirmed:

- The corporate-actions dividend endpoint defines `statement` as a string distribution-plan description. It is corroborating free-text evidence, not a structured numeric amount field: <https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-corporate-actions-dividends.html>.
- The Rehab protocol defines ordinary `dividend` and special `spDividend` fields: <https://openapi.moomoo.com/moomoo-api-doc/en/quote/quote.html>.
- At official SDK commit `dfb09498bdd34bdeb37c12b3cfec6d55908450d9`, `rehab.spDividend` maps to `special_dividend` and `rehab.dividend` maps to `per_cash_div`: <https://github.com/MoomooOpen/py-moomoo-api/blob/dfb09498bdd34bdeb37c12b3cfec6d55908450d9/moomoo/quote/quote_query.py#L1967-L1970>.

The proposed semantic direction is sound: structured Rehab fields should be numeric authority, endpoint evidence should remain mandatory, and endpoint `statement` should never be parsed numerically. The rejection is caused by the integrated evaluator's failure to preserve that fail-closed rule for negative raw values.

## Split normalization and frozen strategy

`CORPORATE-ACTION-NORMALIZATION-CONTRACT-v2` and `src/investment_tracker/quant/successor/corporate_actions_v2.py` have identical Git blobs at the predecessor and reviewed heads.

The frozen survivor identity verifier returned:

- candidate: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`
- binding SHA-256: `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`
- implementation SHA-256: `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`
- status: `SURVIVOR_IMPLEMENTATION_AND_BINDING_FROZEN`

No strategy parameter change was authorized or made.

## Permanent exclusions

`data/governance/holdout-exclusion-registry.json` is `FROZEN`, contains 28 entries and 28 unique identities, and requires no re-entry, no manual exception, pre-ranking application, and performance independence.

The five groups contain 8 research identities plus four consumed/prior-access groups of 5 identities each, including the consumed Generation-3 group. All 28 are permanently excluded.

## Exact reviewed SHA-256 values

| Bound input | SHA-256 |
| --- | --- |
| split contract | `d233aae7f1489d4d3d2ea854a6a2d0e8b473034a1ad4f31effcbdd126f9f1992` |
| dividend contract | `c58ccef02d1cf1c9111e5a8c85a059600ec271f58b6bd557936335d59f5d163b` |
| split normalizer | `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04` |
| dividend reconciliation module | `4c805dca25b4aefbb2c4411572f563f4e6415bf1cbca39799071d7f16c485d79` |
| successor evaluator | `36ea04893936b73aa4f99a7b48167a25dedaebf584f0eecad38c16f583fa86a9` |
| holdout exclusion registry | `e48ccebfeaac367f6fea80457b2e1cba13f63ba051302b8324a59dad3d4c1343` |

These hashes identify the rejected reviewed proposal and are not authorization bindings.

## Tests and gates

The focused command covering split-v2 regressions, dividend reconciliation v3, the successor dividend evaluator, and the post-Generation-3 authority gate completed with `36 passed`.

The dedicated local governance gate also passed:

- three successor files compiled;
- no trade-execution capability markers were present in the governed successor code/tests;
- no Generation-3 protected identities appeared in the governed successor code/tests;
- predecessor closure invariants and old evaluator SHA-256 matched;
- the exclusion registry contained 28 unique identities.

GitHub Actions job `successor-dividend-v3` for PR #35 at `556fd7e` succeeded in 44 seconds: <https://github.com/caspar5911/Investment-Tracker/actions/runs/35820016927/job/107049672999?pr=35>.

Those passing tests and gates do not override the independently reproduced integration defect. The focused suite tests negative amounts only at the standalone reconciliation-helper boundary; its evaluator-level tests cover positive multi-component values and free-text non-authority but not raw negative structured inputs.

## Next permitted action

Engineering may prepare a new, unconsumed review commit that fixes both fail-closed gaps and adds synthetic regressions, without accessing protected history or changing the strategy. Independent Audit may then review that new commit from scratch. No holdout selection, Stage-B/acquisition authorization, protected-history access, Generation-3 retry, Phase-7 action, RECON-009 closure, production approval, or live trading is permitted now.
