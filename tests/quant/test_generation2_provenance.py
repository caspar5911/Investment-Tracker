from __future__ import annotations

from investment_tracker.quant.generation2.provenance import (
    PROVENANCE_SCHEMA,
    FileHash,
    SourceSnapshot,
    reconcile,
    snapshot_content_sha256,
)


def snap(**overrides) -> SourceSnapshot:
    base = dict(
        schema_version=PROVENANCE_SCHEMA,
        provider="MOOMOO",
        acquisition_utc="2026-09-22T00:00:00Z",
        symbols=("GLD", "SPY"),
        range_start="2014-01-01",
        range_end="2022-12-31",
        adjustment_convention="QFQ",
        normalized_file_hashes=(
            FileHash(symbol="GLD", sha256="aaa"),
            FileHash(symbol="SPY", sha256="bbb"),
        ),
        expected_session_authority_sha256="sess-hash",
        transformation_code_version="v1",
        independence="PROVIDER_ORIGIN_EXPORT",
    )
    base.update(overrides)
    return SourceSnapshot(**base)


def separate_provider(**overrides) -> SourceSnapshot:
    base = dict(
        provider="EXCHANGE_FEED",
        independence="SEPARATE_PROVIDER",
    )
    base.update(overrides)
    return snap(**base)


def test_snapshot_hash_is_stable_and_content_sensitive() -> None:
    a = snap()
    b = snap()
    assert snapshot_content_sha256(a) == snapshot_content_sha256(b)
    assert len(snapshot_content_sha256(a)) == 64
    c = snap(symbols=("GLD", "QQQ"))
    assert snapshot_content_sha256(c) != snapshot_content_sha256(a)


def test_matched_independent_snapshot() -> None:
    report = reconcile(snap(), separate_provider())
    assert report.status == "MATCHED"
    assert report.independent_source_established is True
    assert report.mismatches == ()
    assert report.decision_critical is False


def test_symbol_mismatch_is_decision_critical() -> None:
    report = reconcile(snap(), separate_provider(symbols=("GLD", "QQQ")))
    assert report.status == "MISMATCH"
    assert report.decision_critical is True
    assert "symbols" in {item.field for item in report.mismatches}


def test_date_range_mismatch_is_decision_critical() -> None:
    report = reconcile(snap(), separate_provider(range_end="2023-12-31"))
    assert report.status == "MISMATCH"
    assert report.decision_critical is True
    assert "range_end" in {item.field for item in report.mismatches}


def test_adjustment_convention_mismatch_is_decision_critical() -> None:
    report = reconcile(snap(), separate_provider(adjustment_convention="UNADJUSTED"))
    assert report.decision_critical is True
    assert "adjustment_convention" in {item.field for item in report.mismatches}


def test_normalized_hash_mismatch_is_decision_critical() -> None:
    report = reconcile(
        snap(),
        separate_provider(
            normalized_file_hashes=(
                FileHash(symbol="GLD", sha256="aaa"),
                FileHash(symbol="SPY", sha256="CHANGED"),
            )
        ),
    )
    assert report.decision_critical is True
    assert "normalized_file_hashes" in {item.field for item in report.mismatches}


def test_all_mismatches_are_reported() -> None:
    report = reconcile(
        snap(),
        separate_provider(symbols=("GLD", "QQQ"), adjustment_convention="UNADJUSTED"),
    )
    fields = {item.field for item in report.mismatches}
    assert {"symbols", "adjustment_convention"} <= fields


def test_missing_independent_snapshot_is_unknown_abstain() -> None:
    report = reconcile(snap(), None)
    assert report.status == "UNKNOWN_ABSTAIN"
    assert report.independent_source_established is False
    assert report.independent_hash is None


def test_same_provider_does_not_establish_independence() -> None:
    report = reconcile(snap(), snap(independence="SAME_PROVIDER"))
    assert report.status == "UNKNOWN_ABSTAIN"
    assert report.independent_source_established is False


def test_provider_origin_export_establishes_independence() -> None:
    report = reconcile(snap(), snap())
    assert report.status == "MATCHED"
    assert report.independent_source_established is True


def test_non_critical_mismatch_reports_but_not_decision_critical() -> None:
    report = reconcile(snap(), separate_provider(transformation_code_version="v2"))
    assert report.status == "MISMATCH"
    assert report.decision_critical is False
    assert "transformation_code_version" in {item.field for item in report.mismatches}


def test_framework_never_resolves_generation1_limitation() -> None:
    for report in (
        reconcile(snap(), separate_provider()),
        reconcile(snap(), separate_provider(symbols=("GLD", "QQQ"))),
        reconcile(snap(), None),
    ):
        assert report.resolves_generation1_limitation is False
