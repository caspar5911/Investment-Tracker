# Gen2 Phase-6 split normalization root cause and successor remediation

Status: **analysis complete; successor proposal not authorized**

Predecessor closure commit: `f875167f3e758ab3391ff2f961aa740f231568e5`  
Immutable predecessor status: `PHASE6_UNKNOWN_ABSTAIN`  
Recorded failure: `GEN2_PHASE6_SPLIT_RATE_AMBIGUOUS:BNO`

No consumed holdout was reopened, no protected-symbol history was queried, and no performance result was inspected while preparing this report.

## Root cause

The failure was not a strategy-performance failure. The committed Phase-6 closure records that acquisition succeeded, the one-time evaluation release was consumed, no performance result became available, and evaluation terminated fail-closed during corporate-action normalization.

Four distinct issues matter:

1. **Unicode versus ASCII split-rate syntax.** The consumed evaluator's rate parser accepted ASCII `->` (plus legacy `:` and `/`) but not Unicode RIGHTWARDS ARROW U+2192. The incident representation reported to the coordinator included a value such as `1→2`. Official OpenD stock-split documentation shows its documented rate example in ASCII form such as `1->5`. A Unicode-equivalent arrow therefore reached a parser whose grammar did not normalize it first.

2. **Rehab adjustment ratio is not the portfolio share multiplier.** OpenD documents `get_rehab().split_ratio` as numerator/denominator in the adjustment-factor direction. Its documentation states that when 1 share is split into 5 shares, `split_ratio = 1/5`; when 5 shares are joined into 1 share, `split_ratio = 5/1`. A holdings ledger needs the opposite direction: a 1-to-5 forward split multiplies units by 5, and a 5-to-1 reverse split multiplies units by 0.2. Therefore the ledger multiplier is `1 / rehab.split_ratio`, while an endpoint rate `old->new` maps directly to `new / old`.

3. **Historical records outside the evaluation window were parsed too early.** The consumed evaluator parsed every stock-split endpoint rate before determining whether a dated record was relevant to the scored window. Consequently, an irrelevant historical record could terminate the governed evaluation before any decision-relevant event was established. The successor scopes known-dated records to the governed window before strict rate parsing or reconciliation.

4. **US stock-split endpoint records may not carry an ex-date.** Official OpenD documentation marks `ex_date` and `ex_date_str` on the stock-split endpoint as HK-only. For US records, announcement metadata may exist while an effective ex-date is absent. An undated endpoint record cannot safely establish a ledger event date. The successor therefore uses dated `get_rehab().ex_div_date` as the effective-date authority and treats an undated split-endpoint row only as corroboration by a unique normalized multiplier.

## Direction checks

The proposed contract uses the following invariant:

| Event | OpenD endpoint rate | OpenD rehab split_ratio | Ledger unit multiplier |
|---|---:|---:|---:|
| 2-for-1 forward | `1->2` | `1/2 = 0.5` | `2.0` |
| 1-for-5 reverse | `5->1` | `5/1 = 5.0` | `0.2` |

This direction is consistent with public SEC descriptions. A two-for-one split is described as each outstanding share becoming two shares. A 1-for-5 reverse split is described as reducing 10,000 pre-split shares to 2,000 post-split shares.

## Successor reconciliation policy

The proposed `CORPORATE-ACTION-NORMALIZATION-v2` contract:

- applies NFKC Unicode normalization, then maps U+2192 `→` to ASCII `->`;
- accepts only `A->B` and `A→B` in v2 and fails closed on other rate syntaxes;
- interprets endpoint rate as old units to new units and calculates `new/old`;
- interprets rehab `split_ratio` as adjustment ratio and calculates ledger units as its reciprocal;
- uses rehab `ex_div_date` as effective-date authority;
- ignores known-dated provider records outside the governed evaluation window before rate parsing;
- requires in-window dates to be scored sessions;
- requires exact-date + multiplier agreement when the endpoint supplies an ex-date;
- allows an undated endpoint row to corroborate an in-window rehab event only when exactly one unused multiplier match exists;
- never lets an undated endpoint record independently create a ledger event;
- fails closed on missing corroboration, source disagreement, multiple candidate matches, in-window unmatched dated endpoint records, or duplicate decision-relevant events.

The treatment of unmatched undated endpoint rows is a methodology change from the consumed Gen2 evaluator: because OpenD does not provide US ex-dates on this endpoint, unmatched undated rows are recorded as non-bindable rather than assumed to be in-window. This change requires Independent Audit approval before any successor protected evaluation.

## Evidence used

No protected-symbol market history was used.

Official/provider evidence:

- Moomoo OpenAPI, Get Adjustment Factor: https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-rehab.html
- Moomoo OpenAPI, Get Corporate Actions - Stock Splits: https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-corporate-actions-stock-splits.html

Public non-protected evidence:

- SEC two-for-one example: https://www.sec.gov/Archives/edgar/data/1119809/000121390010002529/def14a0610_sunnyside.htm
- SEC 1-for-5 reverse-split mechanics: https://www.sec.gov/Archives/edgar/data/1058307/000149315221006384/formdef14c.htm

Development validation uses synthetic fixtures, including a non-protected `PTSI`-named fixture reflecting the public two-for-one direction. It does not fetch PTSI or any protected history.

## Governance conclusion

The consumed Gen2 Phase-6 status remains unchanged. This remediation is a new proposed methodology and is not a retry authorization. Phase 7 remains unauthorized. RECON-009 remains open. A new virgin holdout/evaluation may occur only after an actual Independent Audit authority approves the successor methodology, decides its formal generation/name, and issues explicit one-time acquisition/evaluation authority.
