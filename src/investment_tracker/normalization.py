from __future__ import annotations

from decimal import Decimal


def normalize_price(raw_price: Decimal, split_factor: Decimal) -> Decimal:
    """Apply frozen NORM-v1 split normalization without guessing a factor."""
    if raw_price <= 0:
        raise ValueError("raw price must be positive")
    if split_factor <= 0:
        raise ValueError("split factor must be positive")
    return raw_price / split_factor


def verify_normalized_price(
    raw_price: Decimal, split_factor: Decimal, normalized_price: Decimal
) -> None:
    if normalize_price(raw_price, split_factor) != normalized_price:
        raise ValueError("NORM-v1 split normalization mismatch")
