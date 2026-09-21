# Generation 2 Independent-Source Provenance Requirement

Date: 2026-09-22

Status: **OPEN PRE-HOLDOUT GATE**

Generation 1 Phase 5 remained `PHASE5_UNKNOWN_ABSTAIN` because
`INDEPENDENT_SOURCE_SNAPSHOT_MISSING`.

Generation 2 must not silently inherit that limitation if the project is to
advance toward decision-grade evidence.

## Required capability

Before Generation-2 final-holdout access, the selected candidate's
TRAIN/VALIDATION evidence must be reproducible from a content-addressed data
snapshot whose provenance is independent of the candidate-selection process.

The snapshot must preserve:

- provider/source identity;
- acquisition timestamp;
- exact symbol set;
- exact requested date range;
- adjustment convention;
- raw-file hashes;
- normalized-file hashes;
- expected-session authority;
- corporate-action source hashes where used;
- transformation/code version.

## Independence rule

A coordinator-generated statement that the data are independent is not
sufficient evidence.

At least one of the following must exist:

1. immutable/provider-origin snapshot or export whose contents can be hashed; or
2. separately acquired independent-source snapshot with documented provider and
   exact reconciliation to the primary research dataset.

If neither is available, research may continue, but the formal limitation
remains UNKNOWN/ABSTAIN and production-readiness approval remains forbidden.

## Reconciliation

Reconciliation must be result-independent and must report all mismatches.

Decision-critical mismatches may not be manually overwritten, averaged, or
selected based on downstream strategy performance.

Missing evidence => UNKNOWN/ABSTAIN.
