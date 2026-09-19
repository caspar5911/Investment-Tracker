from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_tracker.quant.universe.artifacts import (
    ArtifactIntegrityError,
    Phase3ArtifactStore,
)
from investment_tracker.quant.universe.constants import (
    CAMPAIGN_END,
    CAMPAIGN_START,
    CANDIDATE_POOL,
)
from investment_tracker.quant.universe.models import (
    ArtifactIdentity,
    CandidateDQResult,
    DQSnapshot,
    ProviderRequestRecord,
    SelectionResult,
)
from investment_tracker.quant.universe.selection import select_universe


NOW = datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def artifact(kind: str, character: str) -> ArtifactIdentity:
    return ArtifactIdentity(
        kind=kind,
        sha256=character * 64,
        path=f"{kind}/{character * 64}",
    )


def provider_request(symbol: str) -> ProviderRequestRecord:
    return ProviderRequestRecord(
        symbol=symbol,
        code=f"US.{symbol}",
        start=CAMPAIGN_START,
        end=CAMPAIGN_END,
        host="127.0.0.1",
        port=11111,
        ktype="K_DAY",
        autype="qfq",
        fields=("",),
        max_count=1000,
        extended_time=False,
        session="RTH",
    )


def candidate(symbol: str, clean: bool) -> CandidateDQResult:
    return CandidateDQResult(
        symbol=symbol,
        status="PASS" if clean else "FAIL",
        row_count=2264 if clean else 2263,
        provider_request=provider_request(symbol),
        raw_evidence=artifact("raw_provider_evidence", "a"),
        normalized_dataset=artifact("normalized_dataset", "b"),
        quarantine=None if clean else artifact("quarantine", "c"),
        issues=() if clean else ({"code": "MISSING_SESSION", "detail": "2014-01-03"},),
        missing_sessions=(),
        unexpected_sessions=(),
        sdk_version="10.10.7008",
        opend_version="10.10.7008",
        retrieved_at=NOW,
    )


def frozen_snapshot(
    tmp_path: Path,
    clean_symbols: set[str],
    candidate_order: tuple[str, ...] = CANDIDATE_POOL,
) -> tuple[Phase3ArtifactStore, ArtifactIdentity]:
    store = Phase3ArtifactStore(tmp_path / "cache", tmp_path / "results")
    snapshot = DQSnapshot(
        campaign_id="phase3-selection-test",
        window_start=CAMPAIGN_START,
        window_end=CAMPAIGN_END,
        candidate_pool=CANDIDATE_POOL,
        candidates=tuple(
            candidate(symbol, symbol in clean_symbols) for symbol in candidate_order
        ),
        created_at=NOW,
    )
    return store, store.freeze_dq_snapshot(snapshot)


def test_selector_accepts_only_a_frozen_snapshot_and_store() -> None:
    assert tuple(inspect.signature(select_universe).parameters) == (
        "snapshot_identity",
        "store",
    )


def test_selection_rejects_tampered_snapshot(tmp_path: Path) -> None:
    store, frozen = frozen_snapshot(tmp_path, set(CANDIDATE_POOL))
    store.resolve(frozen).write_text("{}", encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        select_universe(frozen, store)


def test_candidate_result_order_cannot_change_selection(tmp_path: Path) -> None:
    clean = {"DIA", "XLK", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLV", "XLI"}
    first_store, first_snapshot = frozen_snapshot(tmp_path / "first", clean)
    second_store, second_snapshot = frozen_snapshot(
        tmp_path / "second", clean, tuple(reversed(CANDIDATE_POOL))
    )

    first = select_universe(first_snapshot, first_store)
    second = select_universe(second_snapshot, second_store)

    assert first.selected_symbols == second.selected_symbols
    assert first.selected_symbols == (
        "DIA", "XLK", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLV"
    )


def test_first_clean_preferred_symbol_wins_without_fallback_inflation(tmp_path: Path) -> None:
    store, snapshot = frozen_snapshot(tmp_path, set(CANDIDATE_POOL))

    result = select_universe(snapshot, store)

    assert result.selected_symbols == (
        "SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP"
    )
    assert "DIA" not in result.selected_symbols
    assert "XLK" not in result.selected_symbols
    assert len(result.selected_symbols) == 8
    assert result.stop_reason == "PHASE_3_UNIVERSE_FROZEN"
    assert result.admitted is True


def test_fallback_and_cyclical_slots_fill_only_when_preceding_slots_fail(tmp_path: Path) -> None:
    clean = {"DIA", "XLK", "IWM", "TLT", "IEF", "GLD", "XLP", "XLI", "XLF"}
    store, snapshot = frozen_snapshot(tmp_path, clean)

    result = select_universe(snapshot, store)

    assert result.selected_symbols == (
        "DIA", "XLK", "IWM", "TLT", "IEF", "GLD", "XLP", "XLI"
    )
    assert "XLF" not in result.selected_symbols
    assert len(result.selected_exposures) == 8
    assert result.selected_exposures[-1].category == "CYCLICAL_EQUITY"


def test_fewer_than_six_slots_fails_closed_with_exact_reason(tmp_path: Path) -> None:
    clean = {"SPY", "QQQ", "TLT", "IEF", "GLD"}
    store, snapshot = frozen_snapshot(tmp_path, clean)

    result = select_universe(snapshot, store)

    assert result.selected_symbols == ("SPY", "QQQ", "TLT", "IEF", "GLD")
    assert result.stop_reason == "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE"
    assert result.admitted is False


def test_selection_result_rejects_performance_inputs() -> None:
    payload = {
        "snapshot": artifact("dq_snapshot", "d").model_dump(mode="json"),
        "decisions": (),
        "selected_exposures": (),
        "selected_symbols": (),
        "admitted": False,
        "stop_reason": "INSUFFICIENT_CLEAN_DIVERSIFIED_UNIVERSE",
        "sharpe": 1.0,
    }

    with pytest.raises(ValidationError, match="sharpe"):
        SelectionResult.model_validate(payload)
