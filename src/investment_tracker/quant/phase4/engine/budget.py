from __future__ import annotations

from investment_tracker.quant.phase4.engine.models import (
    BudgetFamilyReason,
    BudgetState as _BudgetStateModel,
    Gate2SealError,
)
from investment_tracker.quant.phase4.engine.robustness import PERSISTENT_OOS_LIMIT
from investment_tracker.quant.phase4.preregistration.grids import StrategyFamilyDefinition


def _family_ranges(
    families: tuple[StrategyFamilyDefinition, ...],
) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for family in families:
        end = cursor + len(family.candidates)
        ranges.append((cursor, end))
        cursor = end
    return tuple(ranges)


class BudgetState(_BudgetStateModel):
    """Deterministic Phase 4 trial-budget traversal state.

    Three counters are kept distinct and never conflated: the immutable
    population ``budget_positions`` (1..N), the traversal ``traversal_cursor``,
    and the independently advancing ``phase4_new_trials_consumed`` counter.
    Historical Phase 2 lineage trials are frozen context only and never shift
    the Phase 4 consumption ordinal sequence.
    """

    @classmethod
    def from_authority(cls, authority: object) -> "BudgetState":
        grids = authority.grids  # type: ignore[attr-defined]
        families = grids.families
        candidates = grids.candidates
        total = len(candidates)
        return cls(
            candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
            trial_ids=tuple(candidate.trial_id for candidate in candidates),
            budget_positions=tuple(candidate.budget_position for candidate in candidates),
            family_ranges=_family_ranges(families),
            row_states=tuple("UNATTEMPTED" for _ in range(total)),
            consumption_ordinals=tuple(None for _ in range(total)),
            next_consumption_ordinal=1,
            traversal_cursor=0,
            active_family_index=0,
            oos_streak=0,
            campaign_status="ACTIVE",
            campaign_terminated=False,
            last_family_reason=None,
        )

    def consume_current(self, trial_id: str) -> "BudgetState":
        try:
            trial_index = self.trial_ids.index(trial_id)
        except ValueError:
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID",
                "only an authoritative Phase 4 trial may start",
            ) from None
        if self.row_states[trial_index] == "CONSUMED":
            # A duplicate representation is a lookup of immutable consumption
            # state, even when the cursor has moved to another trial.
            return self
        if self.campaign_status != "ACTIVE":
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID", "campaign is not active"
            )
        if self.traversal_cursor >= len(self.trial_ids):
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID", "population already traversed"
            )
        if trial_index != self.traversal_cursor:
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID",
                "only the current cursor trial may start",
            )
        if self.phase4_new_trials_remaining == 0:
            return self.model_copy(update=self._exhaust_aggregate_budget())
        ordinal = self.next_consumption_ordinal
        consumed = self.phase4_new_trials_consumed + 1
        row_states = list(self.row_states)
        row_states[self.traversal_cursor] = "CONSUMED"
        ordinals = list(self.consumption_ordinals)
        ordinals[self.traversal_cursor] = ordinal
        return self.model_copy(
            update={
                "row_states": tuple(row_states),
                "consumption_ordinals": tuple(ordinals),
                "phase4_new_trials_consumed": consumed,
                "phase4_new_trials_remaining": 3000 - consumed,
                "next_consumption_ordinal": consumed + 1,
            }
        )

    def record_candidate_outcome(self, outcome: float | None) -> "BudgetState":
        if self.campaign_status != "ACTIVE":
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID", "campaign is not active"
            )
        if self.row_states[self.traversal_cursor] != "CONSUMED":
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID",
                "outcome requires a consumed current row",
            )
        positive = outcome is not None and outcome > 0
        oos_streak = 0 if positive else self.oos_streak + 1
        updates: dict[str, object] = {"oos_streak": oos_streak}
        _, family_end = self.family_ranges[self.active_family_index]
        if oos_streak >= PERSISTENT_OOS_LIMIT:
            updates.update(self._stop_family(reason="PERSISTENT_OOS_FAILURE"))
        elif self.traversal_cursor == family_end - 1:
            updates.update(self._advance_past_family(reason="EXHAUSTED_GRID"))
        else:
            updates["traversal_cursor"] = self.traversal_cursor + 1
        return self.model_copy(update=updates)

    def terminate_family(self, reason: BudgetFamilyReason) -> "BudgetState":
        """Explicitly end the current family for the given reason.

        Exposed for completeness; :meth:`record_candidate_outcome` already
        drives the two reachable stop reasons (``PERSISTENT_OOS_FAILURE`` and
        ``EXHAUSTED_GRID``) automatically.
        """
        if self.campaign_status != "ACTIVE":
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID", "campaign is not active"
            )
        if reason == "PERSISTENT_OOS_FAILURE":
            updates = self._stop_family(reason=reason)
        elif reason == "EXHAUSTED_GRID":
            updates = self._advance_past_family(reason=reason)
        elif reason == "PER_FAMILY_BUDGET_EXHAUSTED":
            updates = self._stop_family(
                reason=reason,
                skipped_state="SKIPPED_PER_FAMILY_BUDGET",
                include_current=True,
            )
        else:
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID", "unknown family termination reason"
            )
        return self.model_copy(update=updates)

    def fail_campaign(self) -> "BudgetState":
        """Record an unrecoverable system failure: terminate without any
        research stop reason, preserving any already-consumed ordinal."""
        return self.model_copy(
            update={
                "campaign_status": "CAMPAIGN_EXECUTION_FAILED",
                "campaign_terminated": True,
            }
        )

    def _stop_family(
        self,
        *,
        reason: BudgetFamilyReason,
        skipped_state: str = "SKIPPED_FAMILY_STOP",
        include_current: bool = False,
    ) -> dict[str, object]:
        _, family_end = self.family_ranges[self.active_family_index]
        row_states = list(self.row_states)
        first_skipped = self.traversal_cursor if include_current else self.traversal_cursor + 1
        for index in range(first_skipped, family_end):
            if row_states[index] == "UNATTEMPTED":
                row_states[index] = skipped_state
        next_family_index = self.active_family_index + 1
        campaign_status = (
            "COMPLETE" if next_family_index >= len(self.family_ranges) else "ACTIVE"
        )
        return {
            "row_states": tuple(row_states),
            "traversal_cursor": family_end,
            "active_family_index": next_family_index,
            "oos_streak": 0,
            "last_family_reason": reason,
            "campaign_status": campaign_status,
        }

    def _advance_past_family(self, *, reason: BudgetFamilyReason) -> dict[str, object]:
        family_start, family_end = self.family_ranges[self.active_family_index]
        if reason == "EXHAUSTED_GRID" and any(
            state == "UNATTEMPTED"
            for state in self.row_states[family_start:family_end]
        ):
            raise Gate2SealError(
                "BUDGET_ACCOUNTING_INVALID",
                "EXHAUSTED_GRID requires every non-skipped family row to be attempted",
            )
        next_family_index = self.active_family_index + 1
        campaign_status = (
            "COMPLETE" if next_family_index >= len(self.family_ranges) else "ACTIVE"
        )
        return {
            "traversal_cursor": family_end,
            "active_family_index": next_family_index,
            "oos_streak": 0,
            "last_family_reason": reason,
            "campaign_status": campaign_status,
        }

    def _exhaust_aggregate_budget(self) -> dict[str, object]:
        row_states = tuple(
            "SKIPPED_AGGREGATE_BUDGET" if state == "UNATTEMPTED" else state
            for state in self.row_states
        )
        return {
            "row_states": row_states,
            "traversal_cursor": len(self.trial_ids),
            "active_family_index": len(self.family_ranges),
            "oos_streak": 0,
            "campaign_status": "AGGREGATE_BUDGET_EXHAUSTED",
            "campaign_terminated": True,
        }


__all__ = ("BudgetState",)
