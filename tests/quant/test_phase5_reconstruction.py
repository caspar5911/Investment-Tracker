from pathlib import Path

import pandas as pd

from investment_tracker.quant.phase5.methodology import SYMBOLS
from investment_tracker.quant.phase5.reconstruction import replay, summarize


def _frames(count=220):
    idx = pd.bdate_range("2005-01-03", periods=count, tz="UTC")
    qfq = pd.DataFrame(
        {symbol: [100.0 + i * (1.0 + j / 20.0) for i in range(count)] for j, symbol in enumerate(SYMBOLS)},
        index=idx,
    )
    raw_open = qfq * 0.999
    raw_close = qfq.copy()
    raw = pd.concat({"open": raw_open, "close": raw_close}, axis=1)
    rehab = {symbol: {} for symbol in SYMBOLS}
    return raw, qfq, rehab


def test_phase5_first_fill_is_next_open_not_signal_session():
    raw, qfq, rehab = _frames()
    result = replay(raw, qfq, rehab, friction_bps=3)
    assert result.fills
    first_scored = result.sessions[0]
    first_fill = pd.Timestamp(result.fills[0]["session"])
    assert first_fill == result.sessions[1]
    assert first_fill > first_scored


def test_phase5_dq030_remains_unknown():
    raw, qfq, rehab = _frames(520)
    result = replay(raw, qfq, rehab, friction_bps=3)
    meta = {
        "first_common_session": qfq.index[0].strftime("%Y-%m-%d"),
        "last_common_session": qfq.index[-1].strftime("%Y-%m-%d"),
        "common_session_count": len(qfq),
        "common_history_years": 16.0,
        "manifest_sha256": "0" * 64,
    }
    report = summarize(result, qfq, common_meta=meta)
    assert report["max_drawdown"] is None
    assert report["max_drawdown_status"] == "UNKNOWN"
    assert report["calmar"] is None
    assert report["recovery_characteristics"]["reason"] == "DQ-030_UNRESOLVED"


def test_phase5_signal_code_calls_sealed_phase4_algorithm():
    source = Path(__import__("investment_tracker.quant.phase5.reconstruction", fromlist=["x"]).__file__).read_text()
    assert "_cross_sectional_absolute_momentum(binding, signal_history)" in source
