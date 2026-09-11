# Optimizer Phase 1 Repair

## Exact defect

Both `optimizer/search.py::run_search` and
`workflow.py::optimize_cached_universe` treated one candidate's
`robustness_deteriorated=True` result as the family-level stop reason
`ROBUSTNESS_DETERIORATED`. Consequently the first rejected parameter set ended
each deterministic family before later configurations were evaluated.

## Corrected semantics

- Robustness deterioration makes only that candidate ineligible for family
  best and promotion.
- Every evaluated candidate is persisted before the search policy receives its
  result.
- Later deterministic candidates continue to run.
- `PERSISTENT_OOS_FAILURE` occurs after exactly `patience` consecutive
  candidates with `out_of_sample_improved=False`. In the workflow that boolean
  means validation total return did not exceed the matching buy-and-hold total
  return. One improving candidate resets the consecutive-failure counter.
- `NO_MEANINGFUL_IMPROVEMENT` occurs after exactly `patience` consecutive
  candidates fail to exceed the best eligible score by the fixed 0.01 margin.
- `MAX_CANDIDATES` prevents evaluation beyond the configured family budget.
- Exhausting the deterministic generator returns `EXHAUSTED`.

The configured patience remains 50 and the maximum family budget remains 500.
No threshold, score weight or budget was changed after observing results.

## Artifact and rerun status

The four earlier provider-backed experiments remain unchanged and append-only.
They ended under the defective family-stop behavior and therefore require new
experiment IDs in any later rerun. No download, cache refresh, provider call,
external strategy research or holdout access occurred during this repair.
