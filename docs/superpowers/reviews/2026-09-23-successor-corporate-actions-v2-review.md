# Successor corporate-action normalization v2 — second-pass technical review

Status: **TECHNICALLY REVIEWED / NOT INDEPENDENT AUDIT / NOT AUTHORIZED**

This review is intentionally separate from the implementation change, but it is not a substitute for Independent Audit approval.

## Frozen predecessor integrity

Compared against closure commit `f875167f3e758ab3391ff2f961aa740f231568e5`:

- `data/generation2/phase6/phase6-final-holdout-closure.json` blob unchanged: `eb036a2e5a9f8645dd43adf402beb296a315a0c4`
- `data/governance/generation2-phase6-result.json` blob unchanged: `7c6e71a7beaad1064d801591bd0402810124af3a`
- frozen consumed evaluator `src/investment_tracker/independent_audit/generation2/evaluate.py` blob unchanged: `a255be94ae2e6b58251eb8086704c9dda0314adb`

No predecessor status, result, or consumed evaluation implementation was edited.

## Accounting-direction review

Official OpenD adjustment-factor documentation states:

- a 1-share-to-5-share split has rehab `split_ratio = 1/5`;
- a 5-share-to-1-share join has rehab `split_ratio = 5/1`.

Therefore `rehab.split_ratio` is in the opposite direction from a holdings-ledger unit multiplier. The proposed conversion `ledger_multiplier = 1 / split_ratio` is directionally correct.

Official OpenD stock-split endpoint documentation expresses rate as an old-to-new relation, with an example `1->5`. Therefore `endpoint_multiplier = new / old`.

Independent public SEC descriptions are consistent with this:

- two-for-one: each old share becomes two shares;
- 1-for-5 reverse: five old shares become one new share.

Synthetic continuity:

- forward 2-for-1: 100 units × $100 = $10,000; 200 units × $50 = $10,000;
- reverse 1-for-5: 1,000 units × $10 = $10,000; 200 units × $50 = $10,000.

Verdict: **direction logic internally consistent**.

## Reconciliation review

The proposed source hierarchy is coherent with provider field limitations:

1. Rehab `ex_div_date` establishes an effective date.
2. A stock-split endpoint record with an ex-date must agree on both date and normalized multiplier.
3. A stock-split endpoint record without an ex-date cannot establish a ledger event by itself.
4. An undated row may corroborate an in-window rehab event only through a unique unused multiplier match.
5. Multiple matching undated rows are ambiguous and fail closed.
6. A known-dated endpoint record inside the evaluation window without a rehab event fails closed.
7. Known-dated endpoint records outside the evaluation window are excluded before rate parsing because they cannot alter holdings during the governed period.
8. Unmatched undated rows are recorded but not converted into ledger events because OpenD documents US endpoint ex-dates as unavailable.

The last rule is a material methodology change from Gen2. It is technically motivated by the provider schema but must be explicitly approved or rejected by Independent Audit.

Verdict: **suitable for audit review; not self-authorized**.

## Boundaries

- no protected history accessed;
- no holdout performance inspected;
- no strategy tuning;
- no retry or replacement holdout authorized;
- no Phase-7 entry;
- RECON-009 remains open;
- paper/research only.
