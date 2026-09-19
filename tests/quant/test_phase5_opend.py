from pathlib import Path

from investment_tracker.quant.phase5 import opend


def test_opend_source_is_quote_only_and_uses_none_for_execution():
    source = Path(opend.__file__).read_text(encoding="utf-8")
    assert "OpenQuoteContext" in source
    assert "AuType.NONE" in source
    assert "AuType.QFQ" in source
    assert "get_rehab" in source
    assert "OpenSecTradeContext" not in source
    assert "place_order" not in source


def test_qfq_is_separate_from_raw_execution_export():
    source = Path(opend.__file__).read_text(encoding="utf-8")
    assert 'raw_dir = root / "raw"' in source
    assert 'qfq_dir = root / "qfq"' in source
