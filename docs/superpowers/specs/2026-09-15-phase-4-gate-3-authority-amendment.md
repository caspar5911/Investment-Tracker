# Phase 4 Gate 3 Pre-Campaign Authority Amendment

Status: PRE-CAMPAIGN GOVERNANCE DECISION

This amendment was authorized before any Phase 4 candidate execution or
inspection of candidate or validation performance. It binds the two Gate 3
authorities left intentionally unbound by the sealed Gate 2 engine. It does
not amend or replace any Gate 1 or Gate 2 artifact.

## Fixed dependencies

The authority layer must load and byte/hash-verify the exact sealed Gate 1
manifest, exact sealed Gate 2 manifest, frozen Phase 3 universe identity,
frozen Phase 4 split manifest, and the eight immutable Phase 3 normalized
dataset artifacts. Selection by modification time, directory order, or
"latest" discovery is forbidden.

The research universe is exactly, in this order: SPY, QQQ, IWM, TLT, IEF,
GLD, VNQ, XLP. The TRAIN calendar is 2014-01-02 through 2018-12-31 with
1,258 sessions. The VALIDATION calendar is 2019-01-02 through 2022-12-30
with 1,008 sessions. The split manifest's canonical TRAIN and VALIDATION
session digests remain authoritative.

## Calendar-year fold authority

Every frozen VALIDATION session is assigned once, without gaps or overlap,
according only to its UTC calendar year:

- `FOLD_2019`: all 2019 VALIDATION sessions;
- `FOLD_2020`: all 2020 VALIDATION sessions;
- `FOLD_2021`: all 2021 VALIDATION sessions;
- `FOLD_2022`: all 2022 VALIDATION sessions.

The artifact records each fold's first session, final session, session count,
the complete ordered session-to-fold mapping, and its canonical identity.
Strategies retain one fixed rule set and parameter tuple across the folds;
folds never trigger reset, fitting, optimization, or re-optimization.

## Lagged 126-session regime authority

For each VALIDATION session `t` and each of the eight symbols, use only the
frozen QFQ-normalized CLOSE series strictly before `t`:

`lagged_return_i(t) = close_i(t-1) / close_i(t-127) - 1`

This is a 126-session trailing return ending at `t-1`. The current session
close is forbidden. A return greater than zero is positive, a return less
than zero is negative, and an exactly zero return is neither.

- at least six positive symbol returns: `broad_positive_trend`;
- otherwise, at least six negative symbol returns:
  `broad_negative_trend`;
- all other sign combinations: `mixed_cross_asset`.

These are the only regime labels. Earlier TRAIN close observations may be
used solely as lagged warm-up. If any VALIDATION session lacks the exact
history or any required close is unavailable, non-finite, or non-positive,
authority construction fails closed; no session defaults to a regime.

## Narrow data authorization

For authority binding only, code may read the frozen TRAIN/VALIDATION session
metadata and the `timestamp` and `close` columns of the eight exact dataset
artifacts. It may not read another price column, execute a strategy or
portfolio, calculate candidate or benchmark performance, rank or select a
candidate, tune parameters, call a provider, or access FINAL_HOLDOUT or any
protected symbol.

## Immutable evidence and preflight

The new namespace publishes append-only canonical JSON artifacts under
`results/phase4/gate3/` for the fold authority, regime authority, and combined
authority manifest. The manifest is the final write and binds the Gate 1,
Gate 2, universe, split, TRAIN, VALIDATION, fold, regime, and source-commit
identities. Artifact identity is the canonical SHA-256 envelope over kind,
normalized repository-relative POSIX path, and exact-byte content SHA-256.

Preflight loads an explicitly named combined manifest identity; it never
chooses by timestamps or filesystem ordering. It must fail closed on missing,
mutated, noncanonical, incomplete, or mismatched evidence. Success reports:

- fold, regime, friction, neighborhood, bootstrap, and durability authorities
  `BOUND`;
- Gate 1 and Gate 2 `VALID`;
- candidate population `180`;
- Gate 3 `READY`.

The terminal authority status is `GATE3_AUTHORITIES_SEALED`. This status does
not authorize Gate 3 campaign execution.

All approved dependency identities and canonical authority kind/path layouts
must be validated before any manifest-selected reference is dereferenced.
Symlinks, Windows junctions, and other reparse-point redirects are rejected
before reads or writes. A superseded manifest is never accepted by preflight.

## Safety state

At seal and preflight: candidate execution, validation candidate performance
access, ranking, survivor selection, provider calls, downloads, strategy
search, FINAL_HOLDOUT access, protected-symbol access, and trading capability
must all remain false, empty, or zero. Phase 4 trial consumption remains zero.
