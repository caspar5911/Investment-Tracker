# v1-v4 failure diagnosis — research only

## Boundary

This report is development research, not qualification evidence. It uses only
already-seen history. No locked replacement-holdout symbol is accessed, and no
untouched Candidate-v2/v3/v4 Phase-B panel is used.

## Main diagnosis

Candidate v3 was the strongest historical candidate: 83 unique episodes and
RB01-RB08/RB10 PASS, but RB09 failed after dependence control. Candidate v4's
cluster/cooldown hypothesis addressed overlap directly but is not used here as
qualification evidence.

The research question was whether bad pullback entries were occurring too close
to the long-term trend boundary.

### Seen v3 development panel

Panel: XLV/XLP/XLY/XLF/XLRE/XBI/XRT/ITB, 2018-2023.

Candidate-v3 baseline:
- N=83
- median 20d excess vs SPY = +0.0008633
- positive share = 54.2%

With research-only condition close >= 1.05*SMA200:
- N=45
- median 20d excess vs SPY = +0.0135899
- positive share = 66.7%
- 2018-19 median = -0.0033328
- 2020-21 median = +0.0264827
- 2022-23 median = +0.0315752

Winners also had a materially larger median distance above SMA200 than losers
(~7.31% vs ~3.65%).

### Second already-seen development panel

Panel: XLI/XLU/XLB/XME/XOP/IGV/XSD/IYT, 2018-2023. XOP's verified 1-for-4
reverse split at 2020-03-30 was normalized to the post-split basis.

Applying Candidate-v3 signal logic:
- N=127
- median 20d excess vs SPY = +0.0097328
- positive share = 59.8%

Adding close >= 1.05*SMA200:
- N=77
- median 20d excess vs SPY = +0.0180089
- positive share = 71.4%
- 2018-19 median = +0.0211820
- 2020-21 median = +0.0112176
- 2022-23 median = +0.0233442

## Rejected research idea

A short-term relative-strength re-acceleration rule was examined but did not
show a comparably stable separation. It is not carried into Candidate v5.

## Candidate-v5 hypothesis selected

One rule only: Candidate-v3 per-asset logic plus
`asset_close >= 1.05 * asset_sma200`.

The 5% cushion is now frozen before Candidate-v5 panel history is accessed.
No further v5 threshold variants are allowed after the first qualification
request.
