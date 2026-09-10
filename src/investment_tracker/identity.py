from __future__ import annotations

from datetime import date
from decimal import Decimal

from .governance import assert_symbol_allowed


def _date_token(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()


def _number_token(value: int | float | str | Decimal) -> str:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("numeric digest values must be finite")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def canonical_bar_key(asset: str, bar_date: date | str) -> str:
    symbol = assert_symbol_allowed(asset)
    return f"{symbol}|{_date_token(bar_date)}|ALPACA_SIP|NORM-v1"


def raw_digest_token(
    asset: str,
    bar_date: date | str,
    open_raw: int | float | str | Decimal,
    high_raw: int | float | str | Decimal,
    low_raw: int | float | str | Decimal,
    close_raw: int | float | str | Decimal,
    volume_raw: int | float | str | Decimal,
    trade_count_raw: int | float | str | Decimal,
    vwap_raw: int | float | str | Decimal,
) -> str:
    symbol = assert_symbol_allowed(asset)
    values = (
        open_raw,
        high_raw,
        low_raw,
        close_raw,
        volume_raw,
        trade_count_raw,
        vwap_raw,
    )
    return "|".join(
        ["RAWv1", symbol, _date_token(bar_date), *(_number_token(value) for value in values)]
    )
