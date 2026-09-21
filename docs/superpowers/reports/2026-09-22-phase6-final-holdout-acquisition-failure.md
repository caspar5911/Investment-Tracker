# Phase 6 Final Holdout Acquisition Failure

Date: 2026-09-22

Authority: **INDEPENDENT_AUDIT**

## Final status

`PHASE6_UNKNOWN_ABSTAIN`

The Phase 6 replacement-holdout acquisition authorization was consumed and the
historical acquisition failed after first access began.

No retry is authorized for this holdout.

## Frozen identities

Replacement holdout:

- FQAL
- FDMO
- CSB
- FTXO
- VNLA

Evaluation contract SHA-256:

`f92339ae5e82b31350569407c682c5e1853e542810a833321061b6f441489893`

Candidate:

`phase4-d2dbf6f8170a2268972793148db44d29cd42476b65660f136996460bb2d16075`

Acquisition authorization:

`phase6-acquire-c1976ee20b0302152aafdb274882151d`

Authorization CI binding:

- commit: `e93a9d97f846f0dbe6ddaddf0ee009e14e7dbbc1`
- run id: `35634885276`

## Failure

The acquisition command crossed the historical-access boundary and then failed
during validation of the first returned OpenD frame.

Observed exception:

`AttributeError: 'Series' object has no attribute 'normalize'`

Location:

`src/investment_tracker/independent_audit/phase6/opend_qfq.py`

Cause:

`pd.to_datetime(...)` returned a pandas Series, but the validator called
`.normalize()` directly instead of `.dt.normalize()`.

Based on the deterministic acquisition loop order, the first locked symbol
requested was `FQAL`; validation failed before the loop could advance to the
next symbol.

## Governance consequence

The acquisition-start guard had already consumed the authorization before the
provider historical request began.

Therefore:

- historical access has occurred;
- the authorization is consumed;
- no rerun is permitted;
- no replacement/retry is permitted for a better technical or performance result;
- no holdout bundle was successfully sealed;
- no strategy performance was computed;
- no strategy performance was inspected;
- Phase 6 remains `UNKNOWN / ABSTAIN`;
- Phase 7 remains forbidden;
- production readiness remains unapproved.

## Corrective maintenance

The pandas normalization defect was corrected after the consumed failure and a
regression test was added.

The corrective maintenance is for future code safety only and does not reopen
this Phase 6 holdout.
