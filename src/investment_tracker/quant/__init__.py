"""Paper-only ETF quantitative research tools.

This namespace is isolated from canonical tracker mutation and contains no
brokerage or live-trading integration.
"""

from .constants import TRADING_MODE

__all__ = ["TRADING_MODE"]
