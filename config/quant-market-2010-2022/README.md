# Market research run configuration

This immutable run configuration retains the predeclared 2010-2022
TRAIN/VALIDATION dates and includes only ETFs whose complete Moomoo daily QFQ
response passed the XNYS calendar and OHLCV checks without repair: QQQ, TLT,
and IEF.

The other configured ETFs remain in the default universe. They were queried
and rejected or quarantined for provider-side missing or unexpected sessions;
they were not silently repaired, date-shifted, or used in research. The
FINAL_HOLDOUT interval remains declared but inaccessible to ordinary research.
