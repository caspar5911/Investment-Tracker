# Generation-4 Phase-7 prospective snapshot integrity verification

Verified at: 2026-09-29T00:40:06Z

Status: **VERIFIED SNAPSHOT INTEGRITY — PAPER-ONLY PROSPECTIVE EVIDENCE**

This records a read-only integrity verification of the first authorized Phase-7
snapshot. It is not a performance evaluation, checkpoint decision, production
approval, or live-trading authorization. The acquired snapshot bytes and
manifest were not changed. The provider data remains in its local,
content-addressed snapshot directory; this report records its verified
identity without publishing the raw files.

## Bound evidence

- Snapshot: data/phase7/generation4/prospective/snapshots/gen4-phase7-snapshot-09c0946bea22026f08bc572fe58b8c16/
- Snapshot ID: gen4-phase7-snapshot-09c0946bea22026f08bc572fe58b8c16
- Manifest embedded canonical SHA-256: 16e0b046985ae295567923f4543bb0098865fc86c83bbeda605f1bbd1caf8784
- Manifest file-byte SHA-256: 89c3ca5cda6305748333c90bb5135535c34e418251ff371a180c81325475739c
- Evaluation authorization ID: INDEP-AUDIT-GEN4-PHASE7-EVAL-20260929-CODEX-0001
- Evaluation authorization file SHA-256: 35c767097e135319f059060ca01553160f8ae492b9571769a90bafe1a4585812
- Audit request SHA-256: 922e998570f347e9f1c664e28c2ee7a43479cb44ad7932ee59e4151b5f0142d7
- Evaluation contract SHA-256: b1dccfe54762f9e9e13a496e0d574999a5b547ff986d3e7ec1c1ca9b03835f39
- Start artifact SHA-256: 486f3af558e28da9143d7435dc1a1957dc9c2daf4e34005a3e369af9a258c414
- Frozen evaluation implementation commit: 5149ac70d2561abff4b2cc6d2b8c75dbedfa3bd2
- Candidate: G2-A|lookback=189|skip=21|top_k=1|rebalance=21

## Integrity findings

- The manifest parses under GENERATION4-PHASE7-PROSPECTIVE-SNAPSHOT-v1.
  Its embedded SHA-256 matches the canonical manifest body. Its snapshot ID
  recomputes from the authorized request, candidate, universe, and acquisition
  timestamp.
- Exactly 40 data files are listed and present: QFQ, unadjusted, rehab,
  dividend, and split files for each of GLD, IEF, IWM, QQQ, SPY, TLT, VNQ,
  and XLP. Every listed file's actual SHA-256 and byte size matches. The
  symbol-level hashes agree with the file table; no extra snapshot files exist.
- All 16 bar files have exactly the XNYS sessions from 2025-11-24 through
  2026-09-28: 210 warmup sessions and one scored session. They have no duplicate
  or missing sessions, nonfinite or nonpositive prices, negative volume, or
  invalid OHLC relationships. The first scored session is 2026-09-28.
- The frozen path uses QFQ bars for signals and unadjusted bars plus explicit
  corporate actions for execution and P&L. The manifest declares QFQ signals,
  unadjusted execution, and corporate actions included.
- No QQQM, FALN, IIPR, PSTL, or EFAS file exists in the snapshot; none is
  listed. The manifest declares protected_holdout_symbols_accessed=[], and
  the frozen acquisition path iterates only the authorized research universe.
- The content-addressed snapshot is the sole local Phase-7 prospective
  snapshot. The frozen writer uses exclusive file creation, so it cannot
  overwrite an existing snapshot through this governed path.
- performance_computed=false, performance_inspected=false, and
  trading_context_created=false in the manifest. RECON-009=OPEN and
  DQ-030=UNRESOLVED remain bound by the authorization.

## Verification

The read-only verifier checked the manifest schema and canonical hash,
authorization and governance bindings, all 40 file hashes and byte sizes,
the exact file set, XNYS calendar counts, every bar date and OHLC row, and
corporate-action file parsing. It returned PASS with no failures.

The focused snapshot-integrity, accounting-path, data-boundary,
authorization, evaluation-contract, CLI, and durability test modules passed
using synthetic fixtures. Compile checks for the frozen Phase-7 data,
evaluation, CLI, and durability modules passed.

Current scored-session count: **1**. No provider call, additional acquisition,
checkpoint evaluation, real-snapshot strategy return calculation, or prospective
performance inspection occurred during verification. No checkpoint or production
qualification is asserted.
