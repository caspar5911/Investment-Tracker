from __future__ import annotations

from dataclasses import dataclass

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from .models import DataRequest


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class DataValidationReport:
    issues: tuple[DataQualityIssue, ...]

    @property
    def clean(self) -> bool:
        return not self.issues


class DataQualityError(ValueError):
    def __init__(self, report: DataValidationReport):
        self.report = report
        codes = ", ".join(issue.code for issue in report.issues)
        super().__init__(f"market data failed validation: {codes}")


class BarDataValidator:
    def __init__(self, calendar_name: str = "XNYS") -> None:
        self._calendar = xcals.get_calendar(calendar_name)

    def validate(self, frame: pd.DataFrame, request: DataRequest) -> DataValidationReport:
        issues: list[DataQualityIssue] = []
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing_columns:
            issues.append(DataQualityIssue("MISSING_COLUMN", ",".join(missing_columns)))
            return DataValidationReport(tuple(issues))

        if not isinstance(frame.index, pd.DatetimeIndex):
            issues.append(DataQualityIssue("INVALID_TIMESTAMP_INDEX", type(frame.index).__name__))
            return DataValidationReport(tuple(issues))

        if frame.index.has_duplicates:
            duplicates = frame.index[frame.index.duplicated()].astype(str).tolist()
            issues.append(DataQualityIssue("DUPLICATE_TIMESTAMP", ",".join(duplicates)))
        if not frame.index.is_monotonic_increasing:
            issues.append(DataQualityIssue("NON_MONOTONIC_TIMESTAMP", "timestamps must increase"))

        timezone_clean = frame.index.tz is not None and str(frame.index.tz).upper() == "UTC"
        if not timezone_clean:
            issues.append(DataQualityIssue("TIMEZONE_CONFLICT", f"expected UTC, got {frame.index.tz}"))

        numeric = frame.loc[:, REQUIRED_COLUMNS]
        non_numeric = [column for column in REQUIRED_COLUMNS if not pd.api.types.is_numeric_dtype(numeric[column])]
        if non_numeric:
            issues.append(DataQualityIssue("NON_NUMERIC_VALUE", ",".join(non_numeric)))
        else:
            values = numeric.to_numpy(dtype=float)
            if not np.isfinite(values).all():
                issues.append(DataQualityIssue("NON_FINITE_VALUE", "OHLCV contains NaN or infinity"))

            prices = numeric.loc[:, ("open", "high", "low", "close")]
            if (prices < 0).any().any():
                issues.append(DataQualityIssue("NEGATIVE_PRICE", "price must be non-negative"))
            if (numeric["volume"] < 0).any():
                issues.append(DataQualityIssue("NEGATIVE_VOLUME", "volume must be non-negative"))

            finite_rows = np.isfinite(values).all(axis=1)
            safe = numeric.loc[finite_rows]
            invalid_ohlc = (
                (safe["high"] < safe[["open", "close", "low"]].max(axis=1))
                | (safe["low"] > safe[["open", "close", "high"]].min(axis=1))
            )
            if invalid_ohlc.any():
                issues.append(DataQualityIssue("INVALID_OHLC", "high/low do not bound open and close"))

        if timezone_clean:
            expected = pd.DatetimeIndex(
                self._calendar.sessions_in_range(request.start, request.end)
            )
            if expected.tz is None:
                expected = expected.tz_localize("UTC")
            else:
                expected = expected.tz_convert("UTC")
            observed = frame.index.normalize()
            missing = expected.difference(observed)
            unexpected = observed.difference(expected)
            if len(missing):
                issues.append(DataQualityIssue("MISSING_SESSION", ",".join(map(str, missing))))
            if len(unexpected):
                issues.append(DataQualityIssue("UNEXPECTED_SESSION", ",".join(map(str, unexpected))))

        return DataValidationReport(tuple(issues))
