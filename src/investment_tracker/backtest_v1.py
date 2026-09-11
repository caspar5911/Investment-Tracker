"""Governed, paper-only backtesting framework.

BACKTEST-v1.0 is deliberately strategy-agnostic. It consumes frozen,
already-normalized episode observations and a preregistered protocol; it does
not fetch market data, place trades, or mutate candidate rules.

The framework is intentionally harder to pass than a single-period backtest:
- preregistration must predate qualification-data access;
- qualification datasets cannot be recycled after research/other candidates;
- validation folds are chronological, disjoint and embargoed from research;
- exact t+1 execution and H-session close timing are verified;
- all 0/10/25 bps friction scenarios are required;
- primary statistics use 25 bps net returns;
- dependence is controlled with same-session clustering and 20-session
  non-overlap;
- multiple folds, time concentration, cross-asset breadth and an exact sign
  test must all pass;
- an additional 50 bps stress-friction check must survive;
- missing evidence is INCONCLUSIVE, never silently favorable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
from math import comb
import random
from typing import Iterable, Sequence

from .governance import assert_symbol_allowed

BACKTEST_VERSION = "BACKTEST-v1.0"
PRIMARY_HORIZON_TD = 20
REQUIRED_FRICTION_BPS = (0, 10, 25)
PRIMARY_FRICTION_BPS = 25
STRESS_FRICTION_BPS = 50
NONOVERLAP_SESSIONS = 20
MIN_INDEPENDENT_EPISODES = 20
MIN_INDEPENDENT_PER_FOLD = 5
MIN_VALIDATION_FOLDS = 3
MIN_ADEQUATE_ASSETS = 4
MIN_EPISODES_PER_ASSET = 3
MAX_TIME_CONCENTRATION = Decimal("0.50")
MAX_ASSET_CONCENTRATION = Decimal("0.50")
SIGN_TEST_MAX_P = Decimal("0.10")


class BacktestStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class BacktestProtocolError(ValueError):
    """Protocol is invalid or would permit leakage/selection bias."""


class QualificationReuseError(BacktestProtocolError):
    """Qualification data were previously exposed to a different hypothesis."""


@dataclass(frozen=True)
class ValidationFold:
    fold_id: str
    start_date: date
    end_date: date


@dataclass(frozen=True)
class FrozenBacktestProtocol:
    candidate_id: str
    qualification_dataset_id: str
    panel: tuple[str, ...]
    benchmark: str
    research_end_date: date
    folds: tuple[ValidationFold, ...]
    preregistered_at: datetime
    history_accessed_at: datetime
    strategy_version: str
    calculation_version: str
    robustness_version: str
    protocol_digest: str


@dataclass(frozen=True)
class QualificationAttempt:
    candidate_id: str
    qualification_dataset_id: str
    protocol_digest: str
    first_accessed_at: datetime
    purpose: str  # QUALIFICATION / RESEARCH


@dataclass(frozen=True)
class EpisodeObservation:
    candidate_id: str
    qualification_dataset_id: str
    fold_id: str
    episode_id: str
    asset: str
    signal_date: date
    entry_date: date
    horizon_close_date: date
    horizon_td: int
    friction_bps: int
    gross_return: Decimal
    spy_return: Decimal
    cash_return: Decimal
    max_drawdown: Decimal | None
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class BaselineObservation:
    qualification_dataset_id: str
    fold_id: str
    baseline_id: str
    asset: str
    excess_spy_20d: Decimal
    dq_status: str = "CLEAN"


@dataclass(frozen=True)
class IndependentCluster:
    fold_id: str
    entry_date: date
    episode_ids: tuple[str, ...]
    assets: tuple[str, ...]
    net_excess_spy: Decimal
    net_excess_cash: Decimal
    stress50_excess_spy: Decimal
    stress50_excess_cash: Decimal
    max_drawdown: Decimal


@dataclass(frozen=True)
class FoldResult:
    fold_id: str
    independent_count: int
    median_net_excess_spy: Decimal | None
    median_net_excess_cash: Decimal | None
    positive: bool | None


@dataclass(frozen=True)
class BacktestReport:
    version: str
    candidate_id: str
    qualification_dataset_id: str
    status: BacktestStatus
    failures: tuple[str, ...]
    inconclusive_reasons: tuple[str, ...]
    clean_episode_count: int
    independent_episode_count: int
    fold_results: tuple[FoldResult, ...]
    positive_fold_count: int
    median_net_excess_spy: Decimal | None
    median_net_excess_cash: Decimal | None
    median_stress50_excess_spy: Decimal | None
    median_stress50_excess_cash: Decimal | None
    simple_dip_median_excess_spy: Decimal | None
    max_calendar_year_concentration: Decimal | None
    max_asset_concentration: Decimal | None
    adequately_sampled_asset_count: int
    nonnegative_asset_count: int
    sign_test_successes: int
    sign_test_trials: int
    sign_test_one_sided_p: Decimal | None
    bootstrap_median_p05: Decimal | None
    bootstrap_median_p95: Decimal | None
    median_max_drawdown: Decimal | None
    worst_max_drawdown: Decimal | None
    protocol_digest: str


def freeze_backtest_protocol(
    *,
    candidate_id: str,
    qualification_dataset_id: str,
    panel: Sequence[str],
    benchmark: str,
    research_end_date: date,
    folds: Sequence[ValidationFold],
    preregistered_at: datetime,
    history_accessed_at: datetime,
    strategy_version: str,
    calculation_version: str,
    robustness_version: str,
) -> FrozenBacktestProtocol:
    """Create a deterministic preregistration record.

    This function refuses a protocol whose data-access timestamp precedes its
    preregistration timestamp. It does not claim that timestamps alone prove
    non-access; callers should also retain provider/audit logs.
    """
    if not candidate_id or not qualification_dataset_id:
        raise BacktestProtocolError("candidate_id and qualification_dataset_id are required")
    _require_aware(preregistered_at)
    _require_aware(history_accessed_at)
    if history_accessed_at < preregistered_at:
        raise BacktestProtocolError("qualification history access predates preregistration")

    normalized_panel = tuple(assert_symbol_allowed(symbol) for symbol in panel)
    normalized_benchmark = assert_symbol_allowed(benchmark)
    if len(normalized_panel) != len(set(normalized_panel)):
        raise BacktestProtocolError("panel symbols must be unique")
    if normalized_benchmark in normalized_panel:
        raise BacktestProtocolError("benchmark must not also be a panel asset")
    if len(folds) < MIN_VALIDATION_FOLDS:
        raise BacktestProtocolError(
            f"at least {MIN_VALIDATION_FOLDS} validation folds are required"
        )
    _validate_fold_order(folds)

    payload = {
        "candidate_id": candidate_id,
        "qualification_dataset_id": qualification_dataset_id,
        "panel": normalized_panel,
        "benchmark": normalized_benchmark,
        "research_end_date": research_end_date,
        "folds": tuple(folds),
        "preregistered_at": preregistered_at,
        "history_accessed_at": history_accessed_at,
        "strategy_version": strategy_version,
        "calculation_version": calculation_version,
        "robustness_version": robustness_version,
    }
    digest = _digest(payload)
    return FrozenBacktestProtocol(**payload, protocol_digest=digest)


def verify_protocol_digest(protocol: FrozenBacktestProtocol) -> bool:
    payload = asdict(protocol)
    digest = payload.pop("protocol_digest")
    return digest == _digest(payload)


def assert_qualification_dataset_unused(
    protocol: FrozenBacktestProtocol,
    prior_attempts: Iterable[QualificationAttempt],
) -> None:
    """Prevent silent reuse of a qualification dataset after hypothesis exposure.

    A deterministic recomputation of the exact same candidate/protocol is
    allowed. Any prior RESEARCH use or a different candidate/protocol means the
    dataset is no longer untouched qualification evidence.
    """
    for attempt in prior_attempts:
        if attempt.qualification_dataset_id != protocol.qualification_dataset_id:
            continue
        same_protocol = (
            attempt.candidate_id == protocol.candidate_id
            and attempt.protocol_digest == protocol.protocol_digest
            and attempt.purpose == "QUALIFICATION"
        )
        if not same_protocol:
            raise QualificationReuseError(
                "qualification dataset was previously exposed to another "
                "hypothesis or research use"
            )


def validate_protocol_calendar(
    protocol: FrozenBacktestProtocol,
    benchmark_sessions: Sequence[date],
) -> None:
    """Validate chronological folds and the research-to-validation embargo."""
    sessions = _calendar(benchmark_sessions)
    index = {day: i for i, day in enumerate(sessions)}
    if protocol.research_end_date not in index:
        raise BacktestProtocolError("research_end_date absent from benchmark calendar")

    first = protocol.folds[0]
    if first.start_date not in index or first.end_date not in index:
        raise BacktestProtocolError("first validation fold absent from benchmark calendar")
    if index[first.start_date] - index[protocol.research_end_date] <= NONOVERLAP_SESSIONS:
        raise BacktestProtocolError(
            "first validation fold must start after a 20-session embargo"
        )

    previous_end = None
    for fold in protocol.folds:
        if fold.start_date not in index or fold.end_date not in index:
            raise BacktestProtocolError(
                f"fold dates absent from benchmark calendar: {fold.fold_id}"
            )
        if previous_end is not None and index[fold.start_date] <= index[previous_end]:
            raise BacktestProtocolError("validation folds must be strictly disjoint")
        previous_end = fold.end_date


def evaluate_backtest(
    protocol: FrozenBacktestProtocol,
    observations: Iterable[EpisodeObservation],
    baselines: Iterable[BaselineObservation],
    benchmark_sessions: Sequence[date],
    *,
    prior_attempts: Iterable[QualificationAttempt] = (),
    bootstrap_draws: int = 2000,
) -> BacktestReport:
    """Evaluate a frozen candidate under BACKTEST-v1.0.

    PASS is intentionally demanding. Missing/insufficient evidence produces
    INCONCLUSIVE; observed adverse evidence produces FAIL.
    """
    if not verify_protocol_digest(protocol):
        raise BacktestProtocolError("protocol digest mismatch")
    assert_qualification_dataset_unused(protocol, prior_attempts)
    validate_protocol_calendar(protocol, benchmark_sessions)
    if bootstrap_draws < 100:
        raise BacktestProtocolError("bootstrap_draws must be >= 100")

    sessions = _calendar(benchmark_sessions)
    index = {day: i for i, day in enumerate(sessions)}
    folds = {fold.fold_id: fold for fold in protocol.folds}
    panel = set(protocol.panel)

    supplied = list(observations)
    grouped: dict[tuple[str, str], dict[int, EpisodeObservation]] = defaultdict(dict)
    clean_primary_rows: list[EpisodeObservation] = []
    timing_errors: list[str] = []

    for row in supplied:
        asset = assert_symbol_allowed(row.asset)
        if asset not in panel:
            raise BacktestProtocolError(f"asset outside frozen panel: {asset}")
        if row.candidate_id != protocol.candidate_id:
            raise BacktestProtocolError("observation candidate_id mismatch")
        if row.qualification_dataset_id != protocol.qualification_dataset_id:
            raise BacktestProtocolError("observation dataset_id mismatch")
        if row.fold_id not in folds:
            raise BacktestProtocolError(f"unknown fold_id: {row.fold_id}")
        if row.horizon_td != PRIMARY_HORIZON_TD:
            continue
        if row.friction_bps not in REQUIRED_FRICTION_BPS:
            raise BacktestProtocolError("friction must be exactly 0, 10 or 25 bps")
        if row.dq_status != "CLEAN":
            continue

        fold = folds[row.fold_id]
        timing_error = _timing_error(row, fold, index)
        if timing_error:
            timing_errors.append(f"{row.episode_id}:{timing_error}")

        key = (row.fold_id, row.episode_id)
        if row.friction_bps in grouped[key]:
            raise BacktestProtocolError(
                f"duplicate episode/friction identity: {row.fold_id}/{row.episode_id}/{row.friction_bps}"
            )
        grouped[key][row.friction_bps] = row
        if row.friction_bps == PRIMARY_FRICTION_BPS:
            clean_primary_rows.append(row)

    if timing_errors:
        raise BacktestProtocolError(
            "lookahead/timing violation: " + "; ".join(timing_errors[:5])
        )

    incomplete_friction = sorted(
        key for key, rows in grouped.items()
        if set(rows) != set(REQUIRED_FRICTION_BPS)
    )
    inconsistent_scenarios = []
    for key, rows in grouped.items():
        if set(rows) != set(REQUIRED_FRICTION_BPS):
            continue
        anchors = {
            (
                row.asset, row.signal_date, row.entry_date, row.horizon_close_date,
                row.gross_return, row.spy_return, row.cash_return, row.max_drawdown,
            )
            for row in rows.values()
        }
        if len(anchors) != 1:
            inconsistent_scenarios.append(key)
        for friction, row in rows.items():
            expected = row.gross_return - Decimal(friction) / Decimal(10000)
            # One ten-billionth is enough to catch stale/cross-scenario arithmetic
            # while tolerating externally serialized decimal representations.
            if abs(_net(row) - expected) > Decimal("0.0000000001"):
                inconsistent_scenarios.append(key)
                break

    inconclusive: list[str] = []
    failures: list[str] = []
    if incomplete_friction:
        inconclusive.append("incomplete_0_10_25bps_friction_scenarios")
    if inconsistent_scenarios:
        failures.append("inconsistent_friction_scenario_inputs")
    if not clean_primary_rows:
        inconclusive.append("no_clean_primary_horizon_observations")

    missing_drawdown = [row for row in clean_primary_rows if row.max_drawdown is None]
    if missing_drawdown:
        inconclusive.append("max_drawdown_missing_for_clean_primary_observations")

    clusters = _independent_clusters(clean_primary_rows, sessions)
    fold_results = _fold_results(protocol.folds, clusters)
    independent_count = len(clusters)

    if independent_count < MIN_INDEPENDENT_EPISODES:
        inconclusive.append("independent_episode_count_below_20")
    for result in fold_results:
        if result.independent_count < MIN_INDEPENDENT_PER_FOLD:
            inconclusive.append(f"{result.fold_id}:independent_count_below_5")

    spy_values = [row.net_excess_spy for row in clusters]
    cash_values = [row.net_excess_cash for row in clusters]
    stress_spy = [row.stress50_excess_spy for row in clusters]
    stress_cash = [row.stress50_excess_cash for row in clusters]
    drawdowns = [row.max_drawdown for row in clusters]

    median_spy = _median_or_none(spy_values)
    median_cash = _median_or_none(cash_values)
    median_stress_spy = _median_or_none(stress_spy)
    median_stress_cash = _median_or_none(stress_cash)

    if median_spy is not None and median_spy <= 0:
        failures.append("median_25bps_excess_spy_not_positive")
    if median_cash is not None and median_cash <= 0:
        failures.append("median_25bps_excess_cash_not_positive")
    if median_stress_spy is not None and median_stress_spy <= 0:
        failures.append("median_50bps_stress_excess_spy_not_positive")
    if median_stress_cash is not None and median_stress_cash <= 0:
        failures.append("median_50bps_stress_excess_cash_not_positive")

    positive_folds = sum(result.positive is True for result in fold_results)
    if len(fold_results) >= MIN_VALIDATION_FOLDS:
        # Strictly require at least two thirds of folds to have positive median
        # 25-bps excess versus SPY.
        if positive_folds * 3 < len(fold_results) * 2:
            failures.append("fewer_than_two_thirds_validation_folds_positive")

    year_concentration = _concentration(
        [row.entry_date.year for row in clean_primary_rows]
    )
    asset_concentration = _concentration([row.asset for row in clean_primary_rows])
    if year_concentration is not None and year_concentration > MAX_TIME_CONCENTRATION:
        failures.append("calendar_year_concentration_above_50pct")
    if asset_concentration is not None and asset_concentration > MAX_ASSET_CONCENTRATION:
        failures.append("asset_concentration_above_50pct")

    by_asset: dict[str, list[Decimal]] = defaultdict(list)
    for row in clean_primary_rows:
        by_asset[row.asset].append(_net_excess_spy(row))
    adequate = {
        asset: values for asset, values in by_asset.items()
        if len(values) >= MIN_EPISODES_PER_ASSET
    }
    nonnegative_assets = sum(
        1 for values in adequate.values() if _median(values) >= 0
    )
    if len(adequate) < MIN_ADEQUATE_ASSETS:
        inconclusive.append("fewer_than_4_adequately_sampled_assets")
    elif nonnegative_assets * 2 <= len(adequate):
        failures.append("cross_asset_breadth_not_strict_majority_nonnegative")

    clean_baselines = []
    for row in baselines:
        asset = assert_symbol_allowed(row.asset)
        if asset not in panel:
            raise BacktestProtocolError(f"baseline asset outside frozen panel: {asset}")
        if row.qualification_dataset_id != protocol.qualification_dataset_id:
            raise BacktestProtocolError("baseline dataset_id mismatch")
        if row.fold_id not in folds:
            raise BacktestProtocolError(f"baseline unknown fold_id: {row.fold_id}")
        if row.dq_status == "CLEAN":
            clean_baselines.append(row)
    baseline_median = _median_or_none(
        [row.excess_spy_20d for row in clean_baselines]
    )
    if baseline_median is None:
        inconclusive.append("simple_dip_baseline_missing")
    elif median_spy is not None and median_spy < baseline_median:
        failures.append("strategy_underperforms_simple_dip_baseline")

    successes = sum(value > 0 for value in spy_values)
    trials = sum(value != 0 for value in spy_values)
    sign_p = _one_sided_sign_test(successes, trials) if trials else None
    if trials < MIN_INDEPENDENT_EPISODES:
        inconclusive.append("sign_test_effective_trials_below_20")
    elif sign_p is not None and sign_p > SIGN_TEST_MAX_P:
        failures.append("sign_test_not_significant_at_10pct")

    boot_lo, boot_hi = _bootstrap_median_interval(
        spy_values, protocol.protocol_digest, draws=bootstrap_draws
    )

    if failures:
        status = BacktestStatus.FAIL
    elif inconclusive:
        status = BacktestStatus.INCONCLUSIVE
    else:
        status = BacktestStatus.PASS

    return BacktestReport(
        version=BACKTEST_VERSION,
        candidate_id=protocol.candidate_id,
        qualification_dataset_id=protocol.qualification_dataset_id,
        status=status,
        failures=tuple(sorted(set(failures))),
        inconclusive_reasons=tuple(sorted(set(inconclusive))),
        clean_episode_count=len(clean_primary_rows),
        independent_episode_count=independent_count,
        fold_results=tuple(fold_results),
        positive_fold_count=positive_folds,
        median_net_excess_spy=median_spy,
        median_net_excess_cash=median_cash,
        median_stress50_excess_spy=median_stress_spy,
        median_stress50_excess_cash=median_stress_cash,
        simple_dip_median_excess_spy=baseline_median,
        max_calendar_year_concentration=year_concentration,
        max_asset_concentration=asset_concentration,
        adequately_sampled_asset_count=len(adequate),
        nonnegative_asset_count=nonnegative_assets,
        sign_test_successes=successes,
        sign_test_trials=trials,
        sign_test_one_sided_p=sign_p,
        bootstrap_median_p05=boot_lo,
        bootstrap_median_p95=boot_hi,
        median_max_drawdown=_median_or_none(drawdowns),
        worst_max_drawdown=min(drawdowns) if drawdowns else None,
        protocol_digest=protocol.protocol_digest,
    )


def _timing_error(
    row: EpisodeObservation,
    fold: ValidationFold,
    index: dict[date, int],
) -> str | None:
    for name, day in (
        ("signal", row.signal_date),
        ("entry", row.entry_date),
        ("horizon", row.horizon_close_date),
    ):
        if day not in index:
            return f"{name}_date_missing_from_benchmark_calendar"
    if not (fold.start_date <= row.signal_date <= fold.end_date):
        return "signal_outside_validation_fold"
    if not (fold.start_date <= row.entry_date <= fold.end_date):
        return "entry_outside_validation_fold"
    if not (fold.start_date <= row.horizon_close_date <= fold.end_date):
        return "horizon_outside_validation_fold"
    if index[row.entry_date] != index[row.signal_date] + 1:
        return "entry_is_not_next_benchmark_session"
    expected_close_index = index[row.entry_date] + row.horizon_td - 1
    if expected_close_index >= len(index):
        return "horizon_exceeds_calendar"
    if index[row.horizon_close_date] != expected_close_index:
        return "horizon_close_does_not_match_exact_session_count"
    if row.max_drawdown is not None and not (Decimal("-1") <= row.max_drawdown <= 0):
        return "max_drawdown_outside_minus1_to_zero"
    return None


def _independent_clusters(
    rows: Sequence[EpisodeObservation],
    benchmark_sessions: Sequence[date],
) -> list[IndependentCluster]:
    index = {day: i for i, day in enumerate(benchmark_sessions)}
    by_date: dict[date, list[EpisodeObservation]] = defaultdict(list)
    for row in rows:
        by_date[row.entry_date].append(row)

    clustered = []
    for entry_date in sorted(by_date):
        items = sorted(by_date[entry_date], key=lambda row: (row.asset, row.episode_id))
        drawdowns = [row.max_drawdown for row in items if row.max_drawdown is not None]
        if len(drawdowns) != len(items):
            # Missing drawdown is handled as INCONCLUSIVE in the report. Keep
            # the cluster arithmetic available without inventing drawdown.
            cluster_drawdown = Decimal(0)
        else:
            cluster_drawdown = min(drawdowns)
        clustered.append(
            IndependentCluster(
                fold_id=items[0].fold_id,
                entry_date=entry_date,
                episode_ids=tuple(row.episode_id for row in items),
                assets=tuple(row.asset for row in items),
                net_excess_spy=_median([_net_excess_spy(row) for row in items]),
                net_excess_cash=_median([_net_excess_cash(row) for row in items]),
                stress50_excess_spy=_median([
                    row.gross_return - Decimal(STRESS_FRICTION_BPS) / Decimal(10000)
                    - row.spy_return for row in items
                ]),
                stress50_excess_cash=_median([
                    row.gross_return - Decimal(STRESS_FRICTION_BPS) / Decimal(10000)
                    - row.cash_return for row in items
                ]),
                max_drawdown=cluster_drawdown,
            )
        )

    selected: list[IndependentCluster] = []
    next_allowed_index = -1
    for cluster in clustered:
        position = index[cluster.entry_date]
        if position < next_allowed_index:
            continue
        selected.append(cluster)
        next_allowed_index = position + NONOVERLAP_SESSIONS
    return selected


def _fold_results(
    folds: Sequence[ValidationFold],
    clusters: Sequence[IndependentCluster],
) -> list[FoldResult]:
    results = []
    for fold in folds:
        rows = [row for row in clusters if row.fold_id == fold.fold_id]
        spy = _median_or_none([row.net_excess_spy for row in rows])
        cash = _median_or_none([row.net_excess_cash for row in rows])
        positive = None if spy is None else spy > 0
        results.append(FoldResult(fold.fold_id, len(rows), spy, cash, positive))
    return results


def _one_sided_sign_test(successes: int, trials: int) -> Decimal:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid sign-test counts")
    numerator = sum(comb(trials, k) for k in range(successes, trials + 1))
    return Decimal(numerator) / (Decimal(2) ** trials)


def _bootstrap_median_interval(
    values: Sequence[Decimal],
    seed_text: str,
    *,
    draws: int,
) -> tuple[Decimal | None, Decimal | None]:
    if not values:
        return None, None
    seed = int.from_bytes(sha256(seed_text.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    medians = []
    n = len(values)
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(_median(sample))
    medians.sort()
    lo = medians[int((draws - 1) * 0.05)]
    hi = medians[int((draws - 1) * 0.95)]
    return lo, hi


def _net(row: EpisodeObservation) -> Decimal:
    return row.gross_return - Decimal(row.friction_bps) / Decimal(10000)


def _net_excess_spy(row: EpisodeObservation) -> Decimal:
    return _net(row) - row.spy_return


def _net_excess_cash(row: EpisodeObservation) -> Decimal:
    return _net(row) - row.cash_return


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("median requires values")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _median_or_none(values: Sequence[Decimal]) -> Decimal | None:
    return None if not values else _median(values)


def _concentration(values: Sequence[object]) -> Decimal | None:
    if not values:
        return None
    counts: dict[object, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return Decimal(max(counts.values())) / Decimal(len(values))


def _validate_fold_order(folds: Sequence[ValidationFold]) -> None:
    previous_end = None
    seen = set()
    for fold in folds:
        if not fold.fold_id or fold.fold_id in seen:
            raise BacktestProtocolError("fold ids must be non-empty and unique")
        seen.add(fold.fold_id)
        if fold.end_date < fold.start_date:
            raise BacktestProtocolError("fold end must be on/after fold start")
        if previous_end is not None and fold.start_date <= previous_end:
            raise BacktestProtocolError("folds must be chronological and disjoint")
        previous_end = fold.end_date


def _calendar(values: Sequence[date]) -> list[date]:
    sessions = list(values)
    if sessions != sorted(set(sessions)):
        raise BacktestProtocolError(
            "benchmark_sessions must be unique and strictly increasing"
        )
    return sessions


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BacktestProtocolError("timestamps must be timezone-aware")


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
