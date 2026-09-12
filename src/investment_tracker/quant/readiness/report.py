from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from .models import FrozenReadinessModel, ReadinessArtifactIdentity
from .statistics import SearchAwareStatisticResult


class ReadinessReportError(RuntimeError):
    """Raised when a readiness report cannot be rendered from valid evidence."""


class ProtectedTreeDigest(FrozenReadinessModel):
    path: Literal[
        "results/experiments",
        "results/phase3",
        "data/cache/phase3",
    ]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase4ReadinessSummary(FrozenReadinessModel):
    schema_version: Literal["PHASE4-READINESS-SUMMARY-v1"] = (
        "PHASE4-READINESS-SUMMARY-v1"
    )
    status: Literal["PHASE_4_READY"] = "PHASE_4_READY"
    bootstrap_source: ReadinessArtifactIdentity
    phase3_universe: ReadinessArtifactIdentity
    phase3_dq_snapshot: ReadinessArtifactIdentity
    bootstrap_input_vector: ReadinessArtifactIdentity
    bootstrap_audit: ReadinessArtifactIdentity
    trial_authority: ReadinessArtifactIdentity
    split_manifest: ReadinessArtifactIdentity
    campaign_configuration: ReadinessArtifactIdentity
    bootstrap_statistic: Literal[
        "median_daily_equal_weight_portfolio_return"
    ] = "median_daily_equal_weight_portfolio_return"
    bootstrap_sample_size: Literal[1007] = 1007
    bootstrap_negative_count: Literal[288] = 288
    bootstrap_zero_count: Literal[368] = 368
    bootstrap_positive_count: Literal[351] = 351
    bootstrap_interval: tuple[Literal[0.0], Literal[0.0]] = (0.0, 0.0)
    bootstrap_claim_scope: Literal[
        "MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"
    ] = "MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY"
    historical_phase2_trial_count: Literal[136] = 136
    phase4_new_trials_consumed: Literal[0] = 0
    phase4_new_trials_remaining: Literal[3000] = 3000
    maximum_aggregate_new_candidate_trials: Literal[3000] = 3000
    dsr: SearchAwareStatisticResult
    pbo: SearchAwareStatisticResult
    symbols: tuple[str, ...] = Field(min_length=8, max_length=8)
    train_declared_start: date = date(2014, 1, 2)
    train_declared_end: date = date(2018, 12, 31)
    train_actual_start: date = date(2014, 1, 2)
    train_actual_end: date = date(2018, 12, 31)
    train_row_count: Literal[1258] = 1258
    validation_declared_start: date = date(2019, 1, 1)
    validation_declared_end: date = date(2022, 12, 30)
    validation_actual_start: date = date(2019, 1, 2)
    validation_actual_end: date = date(2022, 12, 30)
    validation_row_count: Literal[1008] = 1008
    signal_series: Literal["QFQ"] = "QFQ"
    execution_series: Literal["QFQ_NORMALIZED"] = "QFQ_NORMALIZED"
    decision_grade: Literal[False] = False
    provider_calls: Literal[0] = 0
    external_strategy_research_performed: Literal[False] = False
    strategy_search_executed: Literal[False] = False
    strategy_discovery_authorized: Literal[False] = False
    final_holdout_accessed: Literal[False] = False
    protected_symbols_accessed: tuple[()] = ()
    live_trading_capability: Literal[False] = False
    protected_tree_digests: tuple[ProtectedTreeDigest, ...] = Field(
        min_length=3,
        max_length=3,
    )

    @model_validator(mode="after")
    def validate_summary(self) -> "Phase4ReadinessSummary":
        expected_kinds = {
            "bootstrap_source": "phase2_experiment",
            "phase3_universe": "phase3_universe_manifest",
            "phase3_dq_snapshot": "phase3_dq_snapshot",
            "bootstrap_input_vector": "bootstrap_input_vector",
            "bootstrap_audit": "bootstrap_audit",
            "trial_authority": "trial_authority",
            "split_manifest": "phase4_split_manifest",
            "campaign_configuration": "phase4_campaign_configuration",
        }
        if any(
            getattr(self, name).kind != kind
            for name, kind in expected_kinds.items()
        ):
            raise ValueError("readiness summary artifact kind mismatch")
        if self.dsr.name != "DSR" or self.pbo.name != "PBO":
            raise ValueError("readiness summary search statistics mismatch")
        if (
            self.train_declared_start,
            self.train_declared_end,
            self.train_actual_start,
            self.train_actual_end,
            self.validation_declared_start,
            self.validation_declared_end,
            self.validation_actual_start,
            self.validation_actual_end,
        ) != (
            date(2014, 1, 2),
            date(2018, 12, 31),
            date(2014, 1, 2),
            date(2018, 12, 31),
            date(2019, 1, 1),
            date(2022, 12, 30),
            date(2019, 1, 2),
            date(2022, 12, 30),
        ):
            raise ValueError("readiness summary split boundaries mismatch")
        expected_trees = (
            "data/cache/phase3",
            "results/experiments",
            "results/phase3",
        )
        actual_trees = tuple(item.path for item in self.protected_tree_digests)
        if actual_trees != expected_trees:
            raise ValueError("protected tree digests must be complete and sorted")
        return self


def _artifact_line(name: str, identity: ReadinessArtifactIdentity) -> str:
    return (
        f"- {name}: `{identity.path}`; content_sha256="
        f"`{identity.content_sha256}`; envelope_sha256=`{identity.sha256}`"
    )


def render_readiness_report(summary: Phase4ReadinessSummary) -> str:
    try:
        verified = Phase4ReadinessSummary.model_validate(
            summary.model_dump(mode="json")
        )
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise ReadinessReportError("readiness summary is invalid") from exc

    lines = [
        "# Phase 4 Readiness Audit",
        "",
        "Status: PHASE_4_READY",
        "",
        "## Bootstrap evidence",
        "",
        "- Bootstrap statistic: median daily equal-weight portfolio return",
        "- Sample count: 1,007",
        "- Sign counts: 288 negative, 368 zero, 351 positive",
        "- Reproduced interval: [0.0, 0.0]",
        "- Claim scope: MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY",
        "",
        "## Search-aware boundaries",
        "",
        "- 136 historical Phase 2 trials",
        "- Phase 4 budget consumed: 0 of 3,000",
        f"- DSR: {verified.dsr.interpretation}/{verified.dsr.status} — {verified.dsr.reason}",
        f"- PBO: {verified.pbo.interpretation}/{verified.pbo.status} — {verified.pbo.reason}",
        "",
        "## Frozen temporal split",
        "",
        f"- Symbols: {', '.join(verified.symbols)}",
        "- TRAIN declared: 2014-01-02 through 2018-12-31; actual: 2014-01-02 through 2018-12-31 (1,258 sessions)",
        "- VALIDATION declared: 2019-01-01 through 2022-12-30; actual: 2019-01-02 through 2022-12-30 (1,008 sessions)",
        "",
        "## Methodology and safety",
        "",
        "- QFQ is research-only normalized simulation.",
        "- Signal series: QFQ",
        "- Execution series: QFQ_NORMALIZED",
        "- Decision grade: false",
        "- Provider calls: 0",
        "- External strategy research performed: false",
        "- Strategy search executed: false",
        "- Final holdout accessed: false",
        "- Protected symbols accessed: []",
        "- Live trading capability: false",
        "- No strategy discovery was authorized.",
        "",
        "## Evidence artifacts",
        "",
        _artifact_line("Pinned bootstrap source", verified.bootstrap_source),
        _artifact_line("Phase 3 universe", verified.phase3_universe),
        _artifact_line("Phase 3 DQ snapshot", verified.phase3_dq_snapshot),
        _artifact_line("Bootstrap input vector", verified.bootstrap_input_vector),
        _artifact_line("Bootstrap audit", verified.bootstrap_audit),
        _artifact_line("Trial authority", verified.trial_authority),
        _artifact_line("Split manifest", verified.split_manifest),
        _artifact_line("Campaign configuration", verified.campaign_configuration),
        "",
        "## Protected historical trees",
        "",
        *(
            f"- `{item.path}`: `{item.sha256}`"
            for item in verified.protected_tree_digests
        ),
        "",
    ]
    return "\n".join(lines)
