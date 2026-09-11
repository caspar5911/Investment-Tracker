from __future__ import annotations

from pathlib import Path
import textwrap

from investment_tracker.governance import assert_symbol_allowed

from investment_tracker.quant.promotion import ValidatedSnapshot


class ExportBlockedError(RuntimeError):
    pass


SUPPORTED_FAMILIES = frozenset({"trend", "momentum", "trend_momentum"})


def export_strategy(snapshot: ValidatedSnapshot, destination: Path) -> Path:
    if not isinstance(snapshot, ValidatedSnapshot) or snapshot.status != "VALIDATED_SNAPSHOT":
        raise ExportBlockedError("Moomoo export requires an immutable VALIDATED_SNAPSHOT")
    manifest = snapshot.candidate_manifest
    symbols = tuple(assert_symbol_allowed(symbol) for symbol in manifest.data_manifest_hashes)
    if len(symbols) != 1:
        raise ExportBlockedError("StrategyBase export currently requires exactly one validated symbol")
    if manifest.strategy_family not in SUPPORTED_FAMILIES:
        raise ExportBlockedError("strategy cannot be represented exactly with the documented exporter")
    source = _render(manifest.strategy_family, manifest.strategy_parameters, symbols[0], snapshot.digest)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(source)
    return destination


def _render(
    family: str,
    parameters: dict[str, int | float | str | bool],
    expected_symbol: str,
    snapshot_digest: str,
) -> str:
    allocation_key = "allocation"
    if allocation_key not in parameters:
        raise ExportBlockedError("validated strategy has no fixed allocation")
    allocation = _number(parameters[allocation_key], "allocation")
    if not 0 < allocation <= 1:
        raise ExportBlockedError("validated allocation must be within (0, 1]")
    condition, assignments = _condition(family, parameters)
    return textwrap.dedent(
        f'''\
        # SIMULATION/BACKTEST ONLY. Do not load this strategy in a real-money environment.
        # Validated snapshot: {snapshot_digest}
        # Expected trigger symbol: US.{expected_symbol}
        # Signals use select=2, the completed daily bar; orders are guarded against duplicates.

        class Strategy(StrategyBase):
            def initialize(self):
                declare_strategy_type(AlgoStrategyType.SECURITY)
                self.trigger_symbols()
                self.custom_indicator()
                self.global_variables()

            def trigger_symbols(self):
                self.symbol = declare_trig_symbol()

            def custom_indicator(self):
                pass

            def global_variables(self):
                self.expected_symbol = "{expected_symbol}"
                self.allocation = {allocation!r}
{textwrap.indent(assignments, '                ')}

            def handle_data(self):
                if self.has_pending_order():
                    return
                holding = position_holding_qty(symbol=self.symbol)
                should_hold = self.entry_condition()
                if should_hold and holding <= 0:
                    available = max_qty_to_buy_on_cash(
                        symbol=self.symbol,
                        order_type=OrdType.MKT,
                        order_trade_session_type=TSType.RTH,
                    )
                    qty = floor(available * self.allocation)
                    if qty > 0:
                        place_market(
                            symbol=self.symbol,
                            qty=qty,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.DAY,
                        )
                elif not should_hold and holding > 0:
                    close_positions(symbol=self.symbol, qty=abs(holding))

            def has_pending_order(self):
                pending = request_orderid(
                    symbol=self.symbol,
                    status=["WAITING_SUBMIT", "SUBMITTING", "SUBMITTED", "FILLED_PART"],
                    start="",
                    end="",
                )
                return len(pending) > 0

            def entry_condition(self):
{textwrap.indent(condition, '                ')}
        '''
    )


def _condition(
    family: str,
    parameters: dict[str, int | float | str | bool],
) -> tuple[str, str]:
    assignments: list[str] = []
    checks: list[str] = []
    if family in {"trend", "trend_momentum"}:
        fast = _positive_int(parameters.get("fast_window"), "fast_window")
        slow = _positive_int(parameters.get("slow_window"), "slow_window")
        if fast >= slow:
            raise ExportBlockedError("fast_window must be less than slow_window")
        assignments.extend([f"self.fast_window = {fast}", f"self.slow_window = {slow}"])
        checks.extend([
            "completed_close = bar_close(symbol=self.symbol, bar_type=BarType.K_DAY, select=2, session_type=THType.RTH)",
            "fast_ma = ma(symbol=self.symbol, period=self.fast_window, bar_type=BarType.K_DAY, data_type=DataType.CLOSE, select=2, session_type=THType.RTH)",
            "slow_ma = ma(symbol=self.symbol, period=self.slow_window, bar_type=BarType.K_DAY, data_type=DataType.CLOSE, select=2, session_type=THType.RTH)",
        ])
        trend_expression = "completed_close > slow_ma and fast_ma > slow_ma"
    else:
        trend_expression = "True"

    if family in {"momentum", "trend_momentum"}:
        key = "lookback" if family == "momentum" else "momentum_lookback"
        lookback = _positive_int(parameters.get(key), key)
        if lookback + 2 > 500:
            raise ExportBlockedError("momentum lookback exceeds documented select range")
        assignments.append(f"self.momentum_lookback = {lookback}")
        checks.extend([
            "momentum_close = bar_close(symbol=self.symbol, bar_type=BarType.K_DAY, select=2, session_type=THType.RTH)",
            f"momentum_prior = bar_close(symbol=self.symbol, bar_type=BarType.K_DAY, select={lookback + 2}, session_type=THType.RTH)",
        ])
        momentum_expression = "momentum_close > momentum_prior"
    else:
        momentum_expression = "True"

    if family == "trend":
        expression = trend_expression
    elif family == "momentum":
        expression = momentum_expression
    else:
        expression = f"({trend_expression}) and ({momentum_expression})"
    body = "\n".join([*checks, f"return {expression}"])
    return body, "\n".join(assignments)


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExportBlockedError(f"{name} must be a positive integer")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExportBlockedError(f"{name} must be numeric")
    return float(value)
