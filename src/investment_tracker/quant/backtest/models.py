from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from investment_tracker.quant.constants import ENGINE_VERSION, EXECUTION_CONVENTION


@dataclass(frozen=True)
class ExecutionAssumptions:
    initial_capital: float
    commission_bps: float
    slippage_bps: float
    allow_fractional: bool
    engine_version: str = ENGINE_VERSION
    execution_convention: str = EXECUTION_CONVENTION

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("fees and slippage must be non-negative")


@dataclass(frozen=True)
class Fill:
    timestamp: pd.Timestamp
    side: Literal["BUY", "SELL"]
    quantity: float
    reference_price: float
    fill_price: float
    commission: float
    target_exposure: float


@dataclass(frozen=True)
class Trade:
    timestamp: pd.Timestamp
    quantity: float
    realized_pnl: float


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    cash_curve: pd.Series
    position_curve: pd.Series
    exposure_curve: pd.Series
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    turnover_notional: float
    assumptions: ExecutionAssumptions

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve.iloc[-1])
