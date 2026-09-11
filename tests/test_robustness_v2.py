from datetime import date, timedelta
from decimal import Decimal

import pytest

from investment_tracker.robustness_v2 import (
    DependenceObservation,
    RB09Status,
    build_same_session_clusters,
    evaluate_rb09_v2,
    select_nonoverlap_clusters,
)


def sessions(n=500):
    start = date(2027, 1, 1)
    return [start + timedelta(days=i) for i in range(n)]


def test_same_session_ties_use_median_not_asset_order():
    day = sessions()[0]
    rows = [
        DependenceObservation("ETN-E1", "ETN", day, Decimal("-0.02")),
        DependenceObservation("PWR-E1", "PWR", day, Decimal("0.04")),
    ]
    cluster = build_same_session_clusters(reversed(rows))[0]

    assert cluster.assets == ("ETN", "PWR")
    assert cluster.representative_excess_spy_20d == Decimal("0.01")


def test_nonoverlap_selection_is_exactly_twenty_benchmark_sessions():
    calendar = sessions()
    clusters = build_same_session_clusters([
        DependenceObservation("ETN-E1", "ETN", calendar[5], Decimal("0.01")),
        DependenceObservation("PWR-E1", "PWR", calendar[24], Decimal("0.02")),
        DependenceObservation("VRT-E1", "VRT", calendar[25], Decimal("0.03")),
    ])

    selected = select_nonoverlap_clusters(clusters, calendar)
    assert [row.entry_date for row in selected] == [calendar[5], calendar[25]]


def test_rb09_pass_requires_twenty_clusters_and_nonnegative_median():
    calendar = sessions()
    rows = [
        DependenceObservation(
            f"ETN-E{i}",
            "ETN",
            calendar[i * 20],
            Decimal("0.001"),
        )
        for i in range(20)
    ]
    report = evaluate_rb09_v2(rows, calendar)

    assert report.status == RB09Status.PASS
    assert report.nonoverlap_cluster_count == 20
    assert report.median_nonoverlap_excess_spy_20d == Decimal("0.001")


def test_rb09_is_inconclusive_when_nonoverlap_sample_is_too_small():
    calendar = sessions()
    rows = [
        DependenceObservation(
            f"ETN-E{i}", "ETN", calendar[i * 20], Decimal("0.1")
        )
        for i in range(19)
    ]
    assert evaluate_rb09_v2(rows, calendar).status == RB09Status.INCONCLUSIVE


def test_rb09_fails_when_preregistered_median_is_negative():
    calendar = sessions()
    rows = [
        DependenceObservation(
            f"ETN-E{i}", "ETN", calendar[i * 20], Decimal("-0.001")
        )
        for i in range(20)
    ]
    assert evaluate_rb09_v2(rows, calendar).status == RB09Status.FAIL


def test_locked_holdout_is_rejected_before_dependence_analysis():
    day = sessions()[0]
    with pytest.raises(ValueError, match="locked replacement holdout"):
        build_same_session_clusters([
            DependenceObservation("forbidden", "HACK", day, Decimal("0"))
        ])
