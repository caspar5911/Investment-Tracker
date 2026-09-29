"""Generation-2 research data boundary (C2).

This module loads the *exactly eight* frozen generation-2 research symbols from
the local Phase-3 normalized cache, verifies their content hashes through
:class:`investment_tracker.quant.universe.artifacts.Phase3ArtifactStore`, and
enforces the frozen research window. It is the single entry point through which
the generation-2 campaign may read real research data, so that the
governance invariants below hold for every evaluation:

- **Allowed symbols only.** Only ``GLD IEF IWM QQQ SPY TLT VNQ XLP`` may be
  loaded; any missing or unexpected symbol fails closed.
- **No new provider calls.** Data is read only from the content-hash-verified
  local cache; no prospective/holdout data is ever fetched.
- **Cutoff enforcement.** No bar dated after 2022-12-31 may exist; post-2022
  development data is forbidden.
- **Fixed TRAIN / VALIDATION split.** TRAIN ends 2018-12-31; VALIDATION is
  2019-01-01..2022-12-31. Earlier observations are permitted only as causal
  warm-up for the VALIDATION replay.
- **QFQ research comparability.** Every dataset must be a forward-adjusted
  (QFQ) daily series over the fixed 2014-01-01..2022-12-31 window.
- **Provenance.** A frozen, content-addressed provenance record captures each
  symbol's ``content_sha256`` so the boundary can be sealed as evidence.

The pure assembly/verification logic (``build_research_boundary``) is fully
unit-tested on synthetic data; :func:`load_research_boundary` performs the
content-hash-verified discovery against the real cache and is exercised by a
dedicated smoke test.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_tracker.governance import LOCKED_HOLDOUT, assert_symbol_allowed
from investment_tracker.quant.data.cache import content_hash
from investment_tracker.quant.universe.artifacts import Phase3ArtifactStore
from investment_tracker.quant.universe.constants import (
    CAMPAIGN_END,
    CAMPAIGN_START,
)
from investment_tracker.quant.universe.models import (
    ArtifactIdentity,
    NormalizedDatasetMetadata,
)

from .grid import RESEARCH_SYMBOLS

# Frozen generation-2 research window (from the preregistration).
TRAIN_END = date(2018, 12, 31)
VALIDATION_START = date(2019, 1, 1)
VALIDATION_END = date(2022, 12, 31)
CUTOFF_END = date(2022, 12, 31)

RESEARCH_BOUNDARY_SCHEMA = "GENERATION2-RESEARCH-BOUNDARY-v1"
_RESEARCH_BOUNDARY_STATUS = "FROZEN_BEFORE_CAMPAIGN"

__all__ = [
    "CUTOFF_END",
    "RESEARCH_BOUNDARY_SCHEMA",
    "RESEARCH_SYMBOLS",
    "ResearchBoundary",
    "SymbolDataset",
    "TRAIN_END",
    "VALIDATION_END",
    "VALIDATION_START",
    "build_research_boundary",
    "load_research_boundary",
]


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class SymbolDataset:
    """One research symbol's verified dataset as discovered from the cache."""

    symbol: str
    frame: pd.DataFrame
    metadata: NormalizedDatasetMetadata
    content_sha256: str


class _SymbolProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(gt=0)
    first_date: date
    last_date: date
    window_start: date
    window_end: date
    adjustment: str


class ResearchBoundaryProvenance(BaseModel):
    """Frozen, content-addressed record of the research data boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    status: str
    research_symbols: tuple[str, ...]
    train_end: date
    validation_start: date
    validation_end: date
    cutoff_end: date
    post_2022_development_data_forbidden: bool
    symbols: tuple[_SymbolProvenance, ...]
    provenance_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _require_research_symbol(symbol: str) -> str:
    """Reject any symbol outside the frozen research set or in the holdout."""
    normalized = symbol.strip().upper()
    if normalized in LOCKED_HOLDOUT:
        raise ValueError(f"RESEARCH_BOUNDARY_FORBIDDEN_SYMBOL: {normalized}")
    return assert_symbol_allowed(normalized)


def _check_frame(symbol: str, frame: pd.DataFrame, metadata: NormalizedDatasetMetadata) -> None:
    if not {"open", "close"}.issubset(frame.columns):
        raise ValueError(f"RESEARCH_BOUNDARY_FRAME_COLUMNS_MISSING: {symbol}")
    if frame.empty:
        raise ValueError(f"RESEARCH_BOUNDARY_FRAME_EMPTY: {symbol}")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"RESEARCH_BOUNDARY_FRAME_NOT_SORTED: {symbol}")

    request = metadata.provider_request
    if (request.start, request.end) != (CAMPAIGN_START, CAMPAIGN_END):
        raise ValueError(f"RESEARCH_BOUNDARY_WINDOW_MISMATCH: {symbol}")
    if request.adjustment != "QFQ":
        raise ValueError(f"RESEARCH_BOUNDARY_ADJUSTMENT_MISMATCH: {symbol}")

    dates = frame.index.normalize().date
    last = max(dates)
    first = min(dates)
    if last > CUTOFF_END:
        raise ValueError(
            f"RESEARCH_BOUNDARY_CUTOFF_EXCEEDED: {symbol} last={last} > {CUTOFF_END}"
        )
    if first < CAMPAIGN_START:
        raise ValueError(f"RESEARCH_BOUNDARY_BEFORE_WINDOW: {symbol} first={first}")


def build_research_boundary(
    datasets: dict[str, SymbolDataset],
    *,
    expected_symbols: tuple[str, ...] = RESEARCH_SYMBOLS,
) -> "ResearchBoundary":
    """Assemble and verify the research boundary from per-symbol datasets.

    Fails closed unless ``datasets`` contains *exactly* the expected research
    symbols, each with a valid QFQ frame over the fixed window and no bar
    past the cutoff.
    """
    expected = tuple(_require_research_symbol(s) for s in expected_symbols)
    provided = {_require_research_symbol(symbol) for symbol in datasets}
    if set(provided) != set(expected):
        missing = sorted(set(expected) - provided)
        extra = sorted(provided - set(expected))
        raise ValueError(
            "RESEARCH_BOUNDARY_SYMBOL_MISMATCH: missing="
            f"{missing} extra={extra}"
        )

    provenance_records: list[_SymbolProvenance] = []
    bars: dict[str, pd.DataFrame] = {}
    for symbol in expected:
        dataset = datasets[symbol]
        _check_frame(symbol, dataset.frame, dataset.metadata)
        dates = dataset.frame.index.normalize().date
        provenance_records.append(
            _SymbolProvenance(
                symbol=symbol,
                content_sha256=dataset.content_sha256,
                row_count=len(dataset.frame),
                first_date=min(dates),
                last_date=max(dates),
                window_start=dataset.metadata.provider_request.start,
                window_end=dataset.metadata.provider_request.end,
                adjustment=dataset.metadata.provider_request.adjustment,
            )
        )
        bars[symbol] = dataset.frame

    payload = {
        "schema_version": RESEARCH_BOUNDARY_SCHEMA,
        "status": _RESEARCH_BOUNDARY_STATUS,
        "research_symbols": list(expected),
        "train_end": TRAIN_END.isoformat(),
        "validation_start": VALIDATION_START.isoformat(),
        "validation_end": VALIDATION_END.isoformat(),
        "cutoff_end": CUTOFF_END.isoformat(),
        "post_2022_development_data_forbidden": True,
        "symbols": [record.model_dump(mode="json") for record in provenance_records],
    }
    provenance_sha = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    provenance = ResearchBoundaryProvenance(**payload, provenance_sha256=provenance_sha)
    return ResearchBoundary(provenance=provenance, bars=bars)


@dataclass(frozen=True)
class ResearchBoundary:
    """The verified research data boundary plus its frozen provenance."""

    provenance: ResearchBoundaryProvenance
    bars: dict[str, pd.DataFrame] = field(repr=False)

    @property
    def symbols(self) -> tuple[str, ...]:
        return self.provenance.research_symbols

    def content_sha256(self, symbol: str) -> str:
        for record in self.provenance.symbols:
            if record.symbol == symbol:
                return record.content_sha256
        raise KeyError(symbol)

    def train_bars(self) -> dict[str, pd.DataFrame]:
        """Frames restricted to the TRAIN window (index date <= 2018-12-31).

        This is the only data the campaign's TRAIN ranking may read, so the
        VALIDATION period is genuinely never observed while candidates are
        ranked.
        """
        cutoff = pd.Timestamp(TRAIN_END, tz="UTC")
        return {
            symbol: frame[frame.index.normalize() <= cutoff]
            for symbol, frame in self.bars.items()
        }

    def validation_bars(self) -> dict[str, pd.DataFrame]:
        """Full frames (<= cutoff) for the VALIDATION replay.

        The complete 2014..2022 history is retained so VALIDATION signals have
        their frozen causal warm-up; the campaign then restricts decision
        targets to due-dates in [2019-01-01, 2022-12-31].
        """
        return dict(self.bars)

    def provenance_manifest(self) -> dict:
        payload = self.provenance.model_dump(mode="json")
        return {**payload}


def load_research_boundary(
    evidence_root: Path | str,
    results_root: Path | str,
    *,
    expected_symbols: tuple[str, ...] = RESEARCH_SYMBOLS,
    normalized_root: Path | None = None,
) -> "ResearchBoundary":
    """Discover and load the research boundary from the local Phase-3 cache.

    Scans ``phase3/normalized/sha256/*/metadata.json`` under ``evidence_root``
    (or an explicit ``normalized_root``), resolves the exact expected research
    symbols, and content-hash-verifies each via :class:`Phase3ArtifactStore`
    before assembling the boundary. No provider call is made.
    """
    expected = tuple(_require_research_symbol(s) for s in expected_symbols)
    store = Phase3ArtifactStore(Path(evidence_root), Path(results_root))
    if normalized_root is None:
        normalized_root = Path(evidence_root) / "phase3" / "normalized" / "sha256"
    if not normalized_root.is_dir():
        raise ValueError(f"RESEARCH_BOUNDARY_NORMALIZED_ROOT_MISSING: {normalized_root}")

    discovered: dict[str, SymbolDataset] = {}
    for metadata_path in sorted(normalized_root.glob("*/metadata.json")):
        digest = metadata_path.parent.name
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            symbol = payload["metadata"]["symbol"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"RESEARCH_BOUNDARY_METADATA_INVALID: {metadata_path}") from exc
        if symbol not in expected:
            continue
        if symbol in discovered:
            raise ValueError(f"RESEARCH_BOUNDARY_DUPLICATE_DATASET: {symbol}")
        identity = ArtifactIdentity(
            kind="normalized_dataset",
            sha256=digest,
            path=f"phase3/normalized/sha256/{digest}",
        )
        frame, metadata = store.load_normalized_dataset(identity)
        discovered[symbol] = SymbolDataset(
            symbol=symbol,
            frame=frame,
            metadata=metadata,
            content_sha256=content_hash(frame),
        )

    return build_research_boundary(discovered, expected_symbols=expected)
