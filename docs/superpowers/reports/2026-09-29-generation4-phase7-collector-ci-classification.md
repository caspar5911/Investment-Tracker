# Generation-4 Phase-7 collector CI classification

Audited commit: `9eb2ea9d0277998d14445429bbd25d3fbb6b2f4b`

Audited `tests` run: [36506644342](https://github.com/caspar5911/Investment-Tracker/actions/runs/36506644342)

Comparison commit: `6cb4383c4da39810a57dfdd68eec8d448caa77ba`

Comparison `tests` run: [36504319752](https://github.com/caspar5911/Investment-Tracker/actions/runs/36504319752)

The audited `tests` workflow **failed**. Both failed jobs have the same
failing test IDs and the same pytest failure/error summary lines as the
comparison run, which predates the collector. No Generation-4 Phase-7
collector test appears among the failures. This is a classification of the
red workflow, not a waiver or a claim that the full suite passed.

| Failed job | Audited failure | Comparison | Classification |
| --- | --- | --- | --- |
| `generation2 synthetic rehearsal gate` | `generation2 synthetic-only tests`: two failures in `test_generation2_holdout_exclusion.py`. The legacy tests expect three permanent-exclusion groups and an older symbol set; the frozen registry has five groups. | Same two test IDs and failure lines. | Pre-existing Generation-2 test/registry mismatch; unrelated to Phase-7 collection. The preceding Generation-2 governance fail-closed step passed. |
| `test` | Repository-wide pytest: 36 `FAILED` tests and 123 `ERROR` tests. The same two Generation-2 assertions recur. Other failures concern Phase-4/Phase-3 evidence unavailable on the hosted runner (`results/experiments/`, normalized Phase-3 cache, pinned inputs), and the absent `codex/phase4-gate2` ref. | All 159 failing test IDs and their failure/error summary lines match exactly. | Pre-existing historical test and hosted-runner fixture/ref limitations; unrelated to Phase-7 collection. |

The other two jobs in the audited `tests` run, `runner-static` and
`finalization-static`, passed. The exact-head
[`successor-dividend-normalization-v3` run](https://github.com/caspar5911/Investment-Tracker/actions/runs/36506644353)
passed compilation, focused successor/Generation-4 regression tests, and its
governance boundary step. The exact-head Generation-2 holdout-selection,
Phase-6 independent-audit, Phase-6 preseal, Phase-5 static, and successor
corporate-actions workflows also passed.

**Decision:** The two failures in run 36506644342 are pre-existing and
unrelated to the Generation-4 Phase-7 collector. The full `tests` workflow
remains red. This classification changes no authorization, frozen methodology,
candidate, snapshot, or governance artifact.

Provider-free structural status at classification: the first snapshot
`gen4-phase7-snapshot-09c0946bea22026f08bc572fe58b8c16` is verified,
latest acquired and latest completed XNYS session are both `2026-09-28`,
scored sessions are `1`, the next checkpoint is `63`, and `62` sessions remain.
The collector is ready for the next fully completed XNYS session. Collection
is limited operationally to the first 63 scored sessions. Reaching 63 reports
structural checkpoint readiness only; it does not run performance evaluation.
No provider call, new acquisition, or performance inspection occurred during
this classification.
