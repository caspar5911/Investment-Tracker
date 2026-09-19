# Phase 4 Gate 2 Engine Seal Report

Status: SEALED

- Schema: PHASE4-ENGINE-MANIFEST-v1
- Head revision: 84d032a6478bbcddc94284a69a8a1275791fdd07
- Gate 1 manifest: dd175f7c61a9ea01353f5923c7c407720768553f92c73301e46cbc02b0723a89
- Execution: COMPLETED_BAR_SIGNAL_NEXT_BAR_OPEN on QFQ_NORMALIZED; primary friction 3 bps
- Decision grade: False
- Families: 4; candidates: 180
- Historical Phase 2 trials: 136; Phase 4 trials consumed: 0
- Fold status: FOLD_AUTHORITY_MISSING (Gate 3 requirement)
- Regime status: REGIME_AUTHORITY_MISSING (Gate 3 requirement)

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

Unavailable statistics: max drawdown, calmar, dsr, and pbo remain UNKNOWN (NOT_IMPLEMENTED); QFQ normalized series is not decision-grade.
No Phase 4 train/validation replay, validation metric access, candidate ranking, survivor selection, provider call, or trading capability occurred.
