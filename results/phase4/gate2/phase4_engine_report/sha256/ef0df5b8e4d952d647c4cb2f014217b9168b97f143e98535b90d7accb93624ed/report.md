# Phase 4 Gate 2 Engine Seal Report

Status: PHASE4_ENGINE_SEALED

- Schema: PHASE4-ENGINE-MANIFEST-v1
- Formula: PHASE4-ENGINE-FORMULA-v1
- Head revision: cfb2eac7a46e427814d338cff7522ec4f6870077
- Gate 1 manifest: dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89
- QFQ methodology: ffee9bac3fe329b14d5aebb0f6152f00fc0a86b28d9186c254b5c8f6f8a322fb
- Candidate population: 15a33d6dceb52026661ddfba44a84a88fb306b7f64802c36dc60c6ca189a68b3
- Execution: COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN on QFQ_NORMALIZED; primary friction 3 bps; cases (0, 3, 10, 25, 50) bps
- Decision grade: False
- Families: 4; candidates: 180
- Historical Phase 2 trials: 136; Phase 4 trials consumed: 0
- Fold status: NOT_BOUND_GATE3_REQUIRED (Gate 3 requirement)
- Regime status: NOT_BOUND_GATE3_REQUIRED (Gate 3 requirement)

Synthetic conformance invariants:
- ALL_BINDINGS_CONSTRUCT: PASS
- TARGET_GENERATION_REBALANCE_CLOCK: PASS
- REPLAY_ACCOUNTING: PASS
- FRICTION_CASES: PASS
- METRICS: PASS
- DURABILITY: PASS
- BOOTSTRAP: PASS
- BUDGET_STATE_MACHINE: PASS
- FOLD_AUTHORITY_UNBOUND: PASS
- REGIME_AUTHORITY_UNBOUND: PASS
- BASELINE_COMPARISON_ONLY: PASS
- STATIC_SCAN: PASS

Unavailable statistics: max drawdown and calmar remain UNKNOWN (null); DSR and PBO remain UNKNOWN (NOT_IMPLEMENTED, null); QFQ normalized series is not decision-grade.
No Phase 4 train/validation replay, validation metric access, candidate ranking, survivor selection, provider call, or trading capability occurred.
