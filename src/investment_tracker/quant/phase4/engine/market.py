from __future__ import annotations

from hashlib import sha256
from numbers import Integral, Real
from typing import Final, final

import numpy as np
import pandas as pd

from investment_tracker.quant.phase4.engine.models import Gate2SealError, MarketRole
from investment_tracker.quant.phase4.preregistration.canonical import (
    canonical_json_bytes,
)


_VALID_ROLES: Final = frozenset({"WARMUP", "SCORED"})


def _invalid(message: str) -> Gate2SealError:
    return Gate2SealError("MARKET_PANEL_INVALID", f"market panel {message}")


def _validated_sessions(index: pd.Index, *, frame_name: str) -> pd.DatetimeIndex:
    if not isinstance(index, pd.DatetimeIndex):
        raise _invalid(f"{frame_name} index must be a DatetimeIndex")
    if index.empty:
        raise _invalid(f"{frame_name} sessions must not be empty")
    if index.tz is None or str(index.tz) != "UTC":
        raise _invalid(f"{frame_name} sessions must use UTC")
    if not index.is_unique:
        raise _invalid(f"{frame_name} sessions must be unique")
    if not index.is_monotonic_increasing:
        raise _invalid(f"{frame_name} sessions must be strictly increasing")
    if not bool(np.all(index == index.normalize())):
        raise _invalid(f"{frame_name} sessions must be UTC midnight labels")
    return index.copy(deep=True)


def _validated_symbols(columns: pd.Index, *, frame_name: str) -> tuple[str, ...]:
    symbols = tuple(columns.tolist())
    if not symbols:
        raise _invalid(f"{frame_name} symbols must not be empty")
    if any(not isinstance(symbol, str) or not symbol for symbol in symbols):
        raise _invalid(f"{frame_name} symbols must be nonempty strings")
    if len(set(symbols)) != len(symbols):
        raise _invalid(f"{frame_name} symbols must be unique")
    if symbols != tuple(sorted(symbols)):
        raise _invalid(f"{frame_name} symbols must already be canonical")
    return symbols


def _is_exact_binary64_admission(source: object, admitted: np.float64) -> bool:
    if isinstance(source, (bool, np.bool_)) or not isinstance(source, Real):
        return False
    if isinstance(source, Integral):
        return bool(np.isfinite(admitted)) and int(source) == int(admitted)
    try:
        comparison = source == float(admitted)
        return isinstance(comparison, (bool, np.bool_)) and bool(comparison)
    except (TypeError, ValueError, OverflowError):
        return False


def _validated_values(frame: pd.DataFrame, *, frame_name: str) -> np.ndarray:
    source = frame.to_numpy(copy=True)
    try:
        admitted = np.asarray(source, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _invalid(f"{frame_name} prices cannot be admitted as binary64") from exc
    if admitted.shape != frame.shape:
        raise _invalid(f"{frame_name} price shape changed during admission")
    if any(
        not _is_exact_binary64_admission(original, binary64)
        for original, binary64 in zip(source.flat, admitted.flat, strict=True)
    ):
        raise _invalid(f"{frame_name} prices have ambiguous binary64 coercion")
    if not bool(np.all(np.isfinite(admitted))):
        raise _invalid(f"{frame_name} prices must be finite")
    if not bool(np.all(admitted > 0.0)):
        raise _invalid(f"{frame_name} prices must be strictly positive")
    owned = np.ascontiguousarray(admitted, dtype=np.float64)
    owned.setflags(write=False)
    return owned


def _panel_identity(
    *,
    role: MarketRole,
    symbols: tuple[str, ...],
    sessions: tuple[pd.Timestamp, ...],
    open_values: np.ndarray,
    close_values: np.ndarray,
) -> str:
    payload = {
        "role": role,
        "symbols": list(symbols),
        "sessions": [session.isoformat() for session in sessions],
        "open_prices": [[float(value).hex() for value in row] for row in open_values],
        "close_prices": [[float(value).hex() for value in row] for row in close_values],
    }
    return sha256(canonical_json_bytes(payload)).hexdigest()


@final
class MarketPanel:
    """Immutable, exact-binary64 open/close prices for one panel role."""

    __slots__ = (
        "_symbols",
        "_sessions",
        "_open_values",
        "_close_values",
        "_role",
        "_panel_sha256",
    )

    def __init__(self) -> None:
        raise TypeError("MarketPanel must be constructed with from_frames")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("MarketPanel is immutable")

    @classmethod
    def from_frames(
        cls,
        open_prices: pd.DataFrame,
        close_prices: pd.DataFrame,
        *,
        role: MarketRole,
    ) -> MarketPanel:
        if role not in _VALID_ROLES:
            raise _invalid("role must be WARMUP or SCORED")
        if not isinstance(open_prices, pd.DataFrame) or not isinstance(
            close_prices, pd.DataFrame
        ):
            raise _invalid("inputs must be pandas DataFrames")

        open_snapshot = open_prices.copy(deep=True)
        close_snapshot = close_prices.copy(deep=True)
        open_sessions = _validated_sessions(open_snapshot.index, frame_name="open")
        close_sessions = _validated_sessions(close_snapshot.index, frame_name="close")
        if not open_sessions.equals(close_sessions):
            raise _invalid("open and close sessions must match exactly")

        open_symbols = _validated_symbols(open_snapshot.columns, frame_name="open")
        close_symbols = _validated_symbols(close_snapshot.columns, frame_name="close")
        if open_symbols != close_symbols:
            raise _invalid("open and close symbols must match exactly")

        open_values = _validated_values(open_snapshot, frame_name="open")
        close_values = _validated_values(close_snapshot, frame_name="close")
        sessions = tuple(open_sessions)
        panel = object.__new__(cls)
        object.__setattr__(panel, "_symbols", open_symbols)
        object.__setattr__(panel, "_sessions", sessions)
        object.__setattr__(panel, "_open_values", open_values)
        object.__setattr__(panel, "_close_values", close_values)
        object.__setattr__(panel, "_role", role)
        object.__setattr__(
            panel,
            "_panel_sha256",
            _panel_identity(
                role=role,
                symbols=open_symbols,
                sessions=sessions,
                open_values=open_values,
                close_values=close_values,
            ),
        )
        return panel

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    @property
    def sessions(self) -> tuple[pd.Timestamp, ...]:
        return self._sessions

    @property
    def open_prices(self) -> pd.DataFrame:
        return pd.DataFrame(
            self._open_values.copy(),
            index=pd.DatetimeIndex(self._sessions),
            columns=self._symbols,
        )

    @property
    def close_prices(self) -> pd.DataFrame:
        return pd.DataFrame(
            self._close_values.copy(),
            index=pd.DatetimeIndex(self._sessions),
            columns=self._symbols,
        )

    @property
    def role(self) -> MarketRole:
        return self._role

    @property
    def panel_sha256(self) -> str:
        return self._panel_sha256


@final
class ScoredMarketInput:
    """Warm-up close history paired with a separate scored market panel."""

    __slots__ = ("_indicator_warmup", "_scored", "_combined_close_values")

    def __init__(self) -> None:
        raise TypeError("ScoredMarketInput must be constructed with from_panels")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ScoredMarketInput is immutable")

    @classmethod
    def from_panels(
        cls,
        indicator_warmup: MarketPanel,
        scored: MarketPanel,
    ) -> ScoredMarketInput:
        if not isinstance(indicator_warmup, MarketPanel) or not isinstance(
            scored, MarketPanel
        ):
            raise _invalid("scored input members must be MarketPanel instances")
        if indicator_warmup.role != "WARMUP" or scored.role != "SCORED":
            raise _invalid("scored input panel roles are invalid")
        if indicator_warmup.symbols != scored.symbols:
            raise _invalid("warmup and scored symbols must match exactly")
        if indicator_warmup.sessions[-1] >= scored.sessions[0]:
            raise _invalid("warmup sessions must be strictly before scored sessions")

        combined = np.concatenate(
            (indicator_warmup._close_values, scored._close_values), axis=0
        )
        combined.setflags(write=False)
        market_input = object.__new__(cls)
        object.__setattr__(market_input, "_indicator_warmup", indicator_warmup)
        object.__setattr__(market_input, "_scored", scored)
        object.__setattr__(market_input, "_combined_close_values", combined)
        return market_input

    @property
    def indicator_warmup(self) -> MarketPanel:
        return self._indicator_warmup

    @property
    def scored(self) -> MarketPanel:
        return self._scored

    @property
    def warmup_panel_sha256(self) -> str:
        return self._indicator_warmup.panel_sha256

    @property
    def scored_panel_sha256(self) -> str:
        return self._scored.panel_sha256

    @property
    def combined_close_history(self) -> pd.DataFrame:
        sessions = self._indicator_warmup.sessions + self._scored.sessions
        return pd.DataFrame(
            self._combined_close_values.copy(),
            index=pd.DatetimeIndex(sessions),
            columns=self._scored.symbols,
        )


__all__ = ("MarketPanel", "ScoredMarketInput")
