# Post-Generation-3 successor Independent Audit

Verdict: **APPROVED**

Formal successor name: `GENERATION_4`

Reviewed target:

- PR: `#35`
- audit issue: `#36`
- exact reviewed head: `fe0d8602542c8ab03ac6c0209e25b25e3ddd7541`
- prior rejected head: `556fd7ecae071cdc714d536e642242a354e488ce`
- predecessor closure commit: `df9a0c974a392f414dc9b44551b544aa64e8e7f6`

The two material defects from the prior audit are remediated. This decision is
new and binds the exact files at the reviewed head; no identity from the
rejected review was reused.

## Remediation re-test

### Raw structured dividend validation

`validate_structured_dividend_components` validates the raw ordinary and
special Rehab amounts before `_corporate_actions` applies its positive-only
event filter.

Independent synthetic probes produced:

| Probe | Result |
|---|---|
| ordinary `-1`, special `2`, endpoint present | `SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID` |
| ordinary `-1`, special `0`, endpoint absent | `SUCCESSOR_DIVIDEND_STRUCTURED_AMOUNT_INVALID` |
| ordinary `0`, special `0`, endpoint absent | permitted; no cash event |
| ordinary `0`, special `0`, endpoint present | fail closed: `SUCCESSOR_PHASE6_DIVIDEND_SOURCE_RECONCILIATION_FAILED` |
| statement contains `99.99` and `88.88`, structured amounts `0.25` and `0.10` | ledger amounts remain `0.25` and `0.10` |

The two negative cases cannot degrade into a special-only event or no event.
The endpoint `statement` remains nonempty event corroboration and is not
numeric amount authority.

### Predecessor closure invariant

The post-Generation-3 authority loader now requires all of:

- `status=PHASE6_UNKNOWN_ABSTAIN`;
- `one_time_semantics.holdout_consumed=true`;
- `one_time_semantics.retry_authorized=false`;
- `one_time_semantics.symbol_substitution_authorized=false`;
- `phase7.authorized=false`;
- `recon009_status=OPEN`.

An independently tampered synthetic closure with
`symbol_substitution_authorized=true` failed with
`POST_GEN3_PREDECESSOR_CLOSURE_MISMATCH`.

## Exact reviewed identities

| Bound input | SHA-256 |
|---|---|
| `data/governance/successor/corporate-action-normalization-v2.json` | `d233aae7f1489d4d3d2ea854a6a2d0e8b473034a1ad4f31effcbdd126f9f1992` |
| `data/governance/successor/dividend-reconciliation-v3.json` | `c58ccef02d1cf1c9111e5a8c85a059600ec271f58b6bd557936335d59f5d163b` |
| `src/investment_tracker/quant/successor/corporate_actions_v2.py` | `bfbf0de5bdeb39af3535641570f3f9224f5301abb7db9fffc34c580481cace04` |
| `src/investment_tracker/quant/successor/dividend_reconciliation_v3.py` | `6baa251d51f6f16be602aa82b08fc46665a4ccdd62f68705821c48c8a28ac9bc` |
| `src/investment_tracker/independent_audit/successor/evaluate_dividend_v3.py` | `fb20b368d6d7ac0f698c5ab45e5824aaad73341cccfacc25bc6903b98c9a2b21` |
| `data/governance/holdout-exclusion-registry.json` | `e48ccebfeaac367f6fea80457b2e1cba13f63ba051302b8324a59dad3d4c1343` |

Additional frozen evidence:

- Generation-3 evaluator SHA-256:
  `c933cc2b71bf068f9db1f4656f7fea57ed3a5e0307819abc177897782e63e0ea`;
- Generation-3 closure SHA-256:
  `b186a23947701d46c59b44627e88bf1a974bdc29bb956bd98b92fbfc923372d9`;
- candidate: `G2-A|lookback=189|skip=21|top_k=1|rebalance=21`;
- binding SHA-256:
  `fd482e62e81d6813132f3aef747aecbcb07b5e4960b559dc1253510c95f49c8b`;
- implementation SHA-256:
  `35a3ad8f92598021bbfbd2d5d9337036af525b71f978ab053827c4922da60f1b`.

The split-v2 contract and normalizer, the frozen Generation-3 evaluator, the
Generation-3 closure, and the exclusion registry are byte-unchanged from the
prior reviewed head. The Generation-3 closure and evaluator are also
byte-unchanged from the predecessor closure commit.

The registry contains 28 distinct permanently excluded identities, requires
application before ranking, and permits neither re-entry nor manual exception.
No changed remediation source or synthetic regression fixture contains a
consumed Generation-3 identity. No consumed Generation-3 protected history was
accessed for this audit.

## Methodology evidence

The provider documents `statement` as a distribution-plan description and
documents Rehab `per_cash_div` as dividend per share. The official Python SDK
at commit `dfb09498bdd34bdeb37c12b3cfec6d55908450d9` maps
`rehab.dividend` to `per_cash_div` and `rehab.spDividend` to
`special_dividend`. This supports structured Rehab amount authority and does
not support treating free-text statement contents as the numeric authority.

Sources:

- <https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-corporate-actions-dividends.html>
- <https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-rehab.html>
- <https://github.com/MoomooOpen/py-moomoo-api/blob/dfb09498bdd34bdeb37c12b3cfec6d55908450d9/moomoo/quote/quote_query.py#L2134-L2137>

## Verification

- Dedicated successor suite at the reviewed head: **40 passed**.
- Dedicated GitHub workflow `successor-dividend-normalization-v3`:
  **SUCCESS** for exact head `fe0d8602542c8ab03ac6c0209e25b25e3ddd7541`
  on both push and PR runs.
- Compile and governance-boundary steps: passed in the dedicated workflow.
- A legacy Generation-3 Stage-A test still expects the prior 23-symbol
  registry and causes the separate `successor-corporate-actions-v2` workflow
  to fail. That assertion is obsolete and contradicts the required 28-symbol
  exclusion registry; it is not used by the dedicated post-Generation-3 gate
  and does not alter this methodology verdict.

## Authorization boundary

The committed authorization grants only:

- the `GENERATION_4` methodology bound above; and
- future blind virgin-holdout selection.

It explicitly keeps protected-history access false, requires a future one-time
acquisition authorization, forbids retry and symbol substitution after access,
forbids result-dependent methodology changes, leaves Phase 7 and production
readiness false, leaves `RECON-009` open, and remains paper-only.

This is not Stage-B acquisition authorization. The next permitted action is
blind static-metadata selection of a new virgin holdout under the authorized
methodology and 28-symbol exclusion registry. Historical acquisition remains
forbidden until a separate Independent Audit Stage-B authorization is issued.
