from __future__ import annotations

from dataclasses import dataclass, field
import math

import pandas as pd

from .friction import adverse_fill_price, commission
from .models import ExecutionAssumptions, Fill, Trade


@dataclass
class PortfolioLedger:
    assumptions: ExecutionAssumptions
    cash: float = field(init=False)
    quantity: float = 0.0
    average_cost: float = 0.0
    fills: list[Fill] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    turnover_notional: float = 0.0

    def __post_init__(self) -> None:
        self.cash = float(self.assumptions.initial_capital)

    def equity(self, price: float) -> float:
        return self.cash + self.quantity * price

    def rebalance_at_open(self, timestamp: pd.Timestamp, reference_price: float, target: float) -> None:
        pretrade_equity = self.equity(reference_price)
        desired_value = target * pretrade_equity
        current_value = self.quantity * reference_price
        delta_value = desired_value - current_value
        tolerance = max(1e-10, pretrade_equity * 1e-12)
        if abs(delta_value) <= tolerance:
            return
        if delta_value > 0:
            self._buy(timestamp, reference_price, delta_value, target)
        else:
            self._sell(timestamp, reference_price, -delta_value, target)

    def _buy(self, timestamp: pd.Timestamp, reference_price: float, desired_notional: float, target: float) -> None:
        fill_price = adverse_fill_price(reference_price, "BUY", self.assumptions.slippage_bps)
        fee_rate = self.assumptions.commission_bps / 10_000.0
        quantity = min(desired_notional, self.cash) / (fill_price * (1.0 + fee_rate))
        if not self.assumptions.allow_fractional:
            quantity = math.floor(quantity)
        if quantity <= 0:
            return
        notional = quantity * fill_price
        fee = commission(notional, self.assumptions.commission_bps)
        total_cost = notional + fee
        if total_cost > self.cash + 1e-8:
            raise RuntimeError("buy would make cash negative")
        old_cost = self.average_cost * self.quantity
        self.cash -= total_cost
        self.quantity += quantity
        self.average_cost = (old_cost + total_cost) / self.quantity
        self.turnover_notional += notional
        self.fills.append(Fill(timestamp, "BUY", quantity, reference_price, fill_price, fee, target))

    def _sell(self, timestamp: pd.Timestamp, reference_price: float, desired_notional: float, target: float) -> None:
        fill_price = adverse_fill_price(reference_price, "SELL", self.assumptions.slippage_bps)
        if target == 0:
            quantity = self.quantity
        else:
            quantity = min(self.quantity, desired_notional / fill_price)
            if not self.assumptions.allow_fractional:
                quantity = math.floor(quantity)
        if quantity <= 0:
            return
        notional = quantity * fill_price
        fee = commission(notional, self.assumptions.commission_bps)
        net_proceeds = notional - fee
        realized = net_proceeds - self.average_cost * quantity
        self.cash += net_proceeds
        self.quantity -= quantity
        if abs(self.quantity) <= 1e-12:
            self.quantity = 0.0
            self.average_cost = 0.0
        self.turnover_notional += notional
        self.fills.append(Fill(timestamp, "SELL", quantity, reference_price, fill_price, fee, target))
        self.trades.append(Trade(timestamp, quantity, realized))
