from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from investment_tracker.quant.successor.corporate_actions_v2 import (
    CorporateActionNormalizationError,
    NORMALIZATION_SCHEMA,
    NORMALIZATION_STATUS,
    normalize_endpoint_rate,
    normalize_split_events,
    rehab_adjustment_ratio_to_unit_multiplier,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/governance/successor/corporate-action-normalization-v2.json"
CLOSURE = ROOT / "data/generation2/phase6/phase6-final-holdout-closure.json"
SESSIONS = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]


@pytest.mark.parametrize("rate", ["1->2", "1→2", " 1 → 2 "])
def test_ascii_and_unicode_arrow_normalize_to_same_multiplier(rate: str) -> None:
    parsed = normalize_endpoint_rate(rate)
    assert parsed.normalized_text == "1->2"
    assert parsed.unit_multiplier == pytest.approx(2.0)


def test_unsupported_legacy_separators_fail_closed() -> None:
    for rate in ("1:2", "1/2", "2", "1⇒2"):
        with pytest.raises(
            CorporateActionNormalizationError,
            match="SUCCESSOR_SPLIT_RATE_SYNTAX_UNSUPPORTED",
        ):
            normalize_endpoint_rate(rate)


def test_rehab_ratio_is_adjustment_ratio_not_ledger_multiplier() -> None:
    assert rehab_adjustment_ratio_to_unit_multiplier("0.5") == pytest.approx(2.0)
    assert rehab_adjustment_ratio_to_unit_multiplier("5") == pytest.approx(0.2)


def test_two_for_one_forward_split_reconciles_on_non_protected_development_fixture() -> None:
    result = normalize_split_events(
        symbol="PTSI",
        rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
        endpoint_rows=[{"rate": "1→2"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert result.schema_version == NORMALIZATION_SCHEMA
    assert result.status == NORMALIZATION_STATUS
    assert len(result.events) == 1
    assert result.events[0].unit_multiplier == pytest.approx(2.0)
    assert result.events[0].rehab_adjustment_ratio == pytest.approx(0.5)
    assert result.events[0].endpoint_rate == "1->2"
    assert result.events[0].endpoint_dated is False


def test_one_for_five_reverse_split_reconciles() -> None:
    result = normalize_split_events(
        symbol="SYN_REV",
        rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 5.0}],
        endpoint_rows=[{"rate": "5->1"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert result.events[0].unit_multiplier == pytest.approx(0.2)


def test_dated_source_agreement_passes() -> None:
    result = normalize_split_events(
        symbol="SYN",
        rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
        endpoint_rows=[{"ex_date_str": "2024-01-03", "rate": "1->2"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert result.events[0].endpoint_dated is True


def test_source_multiplier_disagreement_fails_closed() -> None:
    with pytest.raises(
        CorporateActionNormalizationError,
        match="SUCCESSOR_SPLIT_SOURCE_DISAGREEMENT",
    ):
        normalize_split_events(
            symbol="SYN",
            rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
            endpoint_rows=[{"ex_date_str": "2024-01-03", "rate": "1->3"}],
            evaluation_start="2024-01-01",
            evaluation_end="2024-01-31",
            scored_sessions=SESSIONS,
        )


def test_known_dated_historical_event_outside_window_is_ignored_before_rate_parse() -> None:
    result = normalize_split_events(
        symbol="SYN",
        rehab_rows=[{"ex_div_date": "2020-01-03", "split_ratio": "not-used"}],
        endpoint_rows=[{"ex_date_str": "2020-01-03", "rate": "unsupported historical text"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert result.events == ()
    assert result.ignored_dated_endpoint_outside_window == 1
    assert result.ignored_rehab_outside_window == 1


def test_undated_endpoint_can_only_corroborate_unique_dated_rehab_event() -> None:
    result = normalize_split_events(
        symbol="SYN",
        rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
        endpoint_rows=[{"rate": "1->2"}, {"rate": "10->1"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert len(result.events) == 1
    assert result.events[0].unit_multiplier == pytest.approx(2.0)
    assert result.ignored_undated_endpoint_records == 1


def test_undated_endpoint_without_rehab_never_creates_ledger_event() -> None:
    result = normalize_split_events(
        symbol="SYN",
        rehab_rows=[],
        endpoint_rows=[{"rate": "1->2"}],
        evaluation_start="2024-01-01",
        evaluation_end="2024-01-31",
        scored_sessions=SESSIONS,
    )
    assert result.events == ()
    assert result.ignored_undated_endpoint_records == 1


def test_duplicate_undated_candidates_for_in_window_event_are_ambiguous() -> None:
    with pytest.raises(
        CorporateActionNormalizationError,
        match="SUCCESSOR_SPLIT_UNDATED_ENDPOINT_AMBIGUOUS",
    ):
        normalize_split_events(
            symbol="SYN",
            rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
            endpoint_rows=[{"rate": "1->2"}, {"rate": "1→2"}],
            evaluation_start="2024-01-01",
            evaluation_end="2024-01-31",
            scored_sessions=SESSIONS,
        )


def test_duplicate_dated_endpoint_event_fails_closed() -> None:
    with pytest.raises(
        CorporateActionNormalizationError,
        match="SUCCESSOR_SPLIT_DUPLICATE_ENDPOINT_EVENT",
    ):
        normalize_split_events(
            symbol="SYN",
            rehab_rows=[{"ex_div_date": "2024-01-03", "split_ratio": 0.5}],
            endpoint_rows=[
                {"ex_date_str": "2024-01-03", "rate": "1->2"},
                {"ex_date_str": "2024-01-03", "rate": "1->2"},
            ],
            evaluation_start="2024-01-01",
            evaluation_end="2024-01-31",
            scored_sessions=SESSIONS,
        )


def test_duplicate_rehab_effective_date_fails_closed() -> None:
    with pytest.raises(
        CorporateActionNormalizationError,
        match="SUCCESSOR_SPLIT_DUPLICATE_REHAB_EVENT",
    ):
        normalize_split_events(
            symbol="SYN",
            rehab_rows=[
                {"ex_div_date": "2024-01-03", "split_ratio": 0.5},
                {"ex_div_date": "2024-01-03", "split_ratio": 0.5},
            ],
            endpoint_rows=[{"rate": "1->2"}],
            evaluation_start="2024-01-01",
            evaluation_end="2024-01-31",
            scored_sessions=SESSIONS,
        )


def test_in_window_dated_endpoint_without_rehab_fails_closed() -> None:
    with pytest.raises(
        CorporateActionNormalizationError,
        match="SUCCESSOR_SPLIT_ENDPOINT_WITHOUT_REHAB",
    ):
        normalize_split_events(
            symbol="SYN",
            rehab_rows=[],
            endpoint_rows=[{"ex_date_str": "2024-01-03", "rate": "1->2"}],
            evaluation_start="2024-01-01",
            evaluation_end="2024-01-31",
            scored_sessions=SESSIONS,
        )


def test_contract_is_unapproved_and_preserves_predecessor_closure() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    assert contract["status"] == "PROPOSED_AWAITING_INDEPENDENT_AUDIT"
    assert contract["authority"] == "COORDINATOR_DRAFT_ONLY"
    assert contract["protected_data"]["historical_access_authorized"] is False
    assert contract["successor_naming"]["generation_or_formal_name"] == (
        "UNDECIDED_REQUIRES_INDEPENDENT_AUDIT"
    )
    assert closure["status"] == "PHASE6_UNKNOWN_ABSTAIN"
    assert closure["evaluation"]["one_time_consumed"] is True
    assert closure["phase7"]["authorized"] is False
    assert closure["recon009_status"] == "OPEN"
