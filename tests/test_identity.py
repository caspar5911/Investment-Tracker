from datetime import date

from investment_tracker.identity import canonical_bar_key, raw_digest_token


def test_canonical_bar_key_uses_semantic_identity():
    assert canonical_bar_key("ura", date(2018, 1, 2)) == "URA|2018-01-02|ALPACA_SIP|NORM-v1"


def test_raw_digest_uses_integer_safe_numeric_tokens():
    token = raw_digest_token(
        "URA",
        date(2018, 1, 2),
        15.14,
        15.74,
        15.12,
        15.68,
        609218.0,
        2530.0,
        15.495505,
    )
    assert token == "RAWv1|URA|2018-01-02|15.14|15.74|15.12|15.68|609218|2530|15.495505"
    assert "609218.0" not in token
    assert "2530.0" not in token
