from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


CAMPAIGN_SPEC_VERSION: Final = "PHASE3-ETF-DQ-SPEC-v1"
CAMPAIGN_START: Final = date(2014, 1, 1)
CAMPAIGN_END: Final = date(2022, 12, 31)
CANDIDATE_POOL: Final = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLP",
    "XLY",
    "XLU",
    "VNQ",
    "TLT",
    "IEF",
    "GLD",
)
MIN_UNIVERSE_SIZE: Final = 6
MAX_UNIVERSE_SIZE: Final = 8

PROVIDER_REQUEST_SCHEMA_VERSION: Final = "MOOMOO-HISTORY-REQUEST-v1"
RAW_EVIDENCE_SCHEMA_VERSION: Final = "MOOMOO-RAW-EVIDENCE-v1"
NORMALIZED_DATASET_SCHEMA_VERSION: Final = "PHASE3-NORMALIZED-DATASET-v1"
NORMALIZATION_VERSION: Final = "MOOMOO-US-DAILY-EASTERN-DATE-UTC-v1"
VALIDATOR_VERSION: Final = "XNYS-OHLCV-DQ-v1"
CALENDAR_SOURCE_VERSION: Final = "exchange_calendars-XNYS-v1"
DQ_SNAPSHOT_SCHEMA_VERSION: Final = "PHASE3-DQ-SNAPSHOT-v1"
DQ_REPORT_SCHEMA_VERSION: Final = "PHASE3-DQ-REPORT-v1"
SELECTION_POLICY_VERSION: Final = "PHASE3-EXPOSURE-SELECTION-v1"
UNIVERSE_MANIFEST_SCHEMA_VERSION: Final = "PHASE3-UNIVERSE-MANIFEST-v1"


@dataclass(frozen=True)
class ExposureSlot:
    name: str
    candidates: tuple[str, ...]
    conditional: bool = False


EXPOSURE_SLOTS: Final = (
    ExposureSlot("BROAD_US_EQUITY", ("SPY", "DIA")),
    ExposureSlot("GROWTH_TECHNOLOGY", ("QQQ", "XLK")),
    ExposureSlot("SMALL_CAP", ("IWM",)),
    ExposureSlot("LONG_TREASURY", ("TLT",)),
    ExposureSlot("INTERMEDIATE_TREASURY", ("IEF",)),
    ExposureSlot("GOLD", ("GLD",)),
    ExposureSlot("REAL_ESTATE", ("VNQ",)),
    ExposureSlot("DEFENSIVE_EQUITY", ("XLP", "XLV", "XLU")),
    ExposureSlot("CYCLICAL_EQUITY", ("XLI", "XLF", "XLE", "XLY"), conditional=True),
)

