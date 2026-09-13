# Phase 4 Gate 1 Research Notes

This preregistration uses literature for mechanism and falsifiable rule design only. No reported performance number selected a parameter, and no Phase 4 validation information was used.

## Evidence synthesis

### A Century of Evidence on Trend-Following Investing

- Citation: Brian K. Hurst, Yao Hua Ooi, Lasse Heje Pedersen (2017), The Journal of Portfolio Management. https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Trend behavior may recur as investors adjust slowly and manage risk under constraints.
- Transfer limits: Firm-authored reconstruction, futures leverage/shorting, and survivorship assumptions do not establish ETF executability.
- Frozen-universe relevance: Motivates regime and calendar durability reporting while preserving strict ETF transfer caveats.

### Time Series Momentum

- Citation: Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen (2012), Journal of Financial Economics. https://doi.org/10.1016/j.jfineco.2011.11.003
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Persistent information diffusion and position adjustment can create continuation followed by longer-horizon reversal.
- Transfer limits: Uses futures, includes long and short positions, and does not establish ETF execution economics or QFQ fill realism.
- Frozen-universe relevance: Supports own-history directional signals, subject to long-only ETF and common-history transfer limits.

### Value and Momentum Everywhere

- Citation: Clifford S. Asness, Tobias J. Moskowitz, Lasse Heje Pedersen (2013), The Journal of Finance. https://doi.org/10.1111/jofi.12021
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Behavioral underreaction and common risk exposures may generate momentum across markets.
- Transfer limits: Many tests are long-short and use broader instrument sets; an eight-ETF long-only rotation is a constrained transfer.
- Frozen-universe relevance: Supports predeclaring relative ranking while requiring cash rather than short exposure for weak assets.

### The Properties of Equally Weighted Risk Contribution Portfolios

- Citation: Sébastien Maillard, Thierry Roncalli, Jérôme Teïletche (2010), The Journal of Portfolio Management. https://doi.org/10.3905/JPM.2010.36.4.060
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Balancing risk contributions can limit concentration that capital weighting may conceal.
- Transfer limits: Full equal-risk contribution requires covariance optimization; inverse-volatility weighting is only a simpler related approximation.
- Frozen-universe relevance: Supports examining transparent risk balancing among admitted long-only ETFs.

### Time Series Momentum: Is It There?

- Citation: Dashan Huang, Jiangyuan Li, Liyao Wang, Guofu Zhou (2020), Journal of Financial Economics. https://doi.org/10.1016/j.jfineco.2019.08.004
- Role: COUNTEREVIDENCE; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Apparent predictability may be sensitive to inference, specification, and sample construction.
- Transfer limits: Its futures tests do not directly settle long-only ETF behavior, but they weaken broad generalization.
- Frozen-universe relevance: Requires fail-closed validation, neighboring-parameter stability, and no assumption that trend must work.

### A Quantitative Approach to Tactical Asset Allocation

- Citation: Mebane T. Faber (2007), The Journal of Wealth Management. https://doi.org/10.3905/jwm.2007.674809
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: A slow trend filter may reduce exposure during persistent adverse regimes.
- Transfer limits: Historical proxy series, simplified implementation, and publication-era costs do not prove current ETF results.
- Frozen-universe relevance: Directly motivates a simple long-only trend-filtered multi-asset allocation comparator.

### Volatility-Managed Portfolios

- Citation: Alan Moreira, Tyler Muir (2017), The Journal of Finance. https://doi.org/10.1111/jofi.12513
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Risk rises more than expected return in some high-volatility states, motivating lower exposure.
- Transfer limits: Some applications imply leverage or factor portfolios; Gate 1 caps gross exposure at one and may hold cash.
- Frozen-universe relevance: Supports testing unlevered lagged volatility scaling of a long-only ETF selection.

### Momentum Has Its Moments

- Citation: Pedro Barroso, Pedro Santa-Clara (2015), Journal of Financial Economics. https://doi.org/10.1016/j.jfineco.2014.11.010
- Role: SUPPORT; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Momentum crash risk is state dependent and can be moderated by exposure scaling.
- Transfer limits: Long-short equity momentum differs materially from unlevered ETF rotation and may not transfer.
- Frozen-universe relevance: Provides mechanism support and a warning to measure friction and crash robustness for momentum allocation.

### On the Performance of Volatility-Managed Portfolios

- Citation: Scott Cederburg, Michael S. O'Doherty, Feifei Wang, Xuemin (Sterling) Yan (2020), Journal of Financial Economics. https://doi.org/10.1016/j.jfineco.2020.04.015
- Role: COUNTEREVIDENCE; tier: PEER_REVIEWED_ACADEMIC.
- Mechanism: Benefits can depend on whether expected return co-moves sufficiently with volatility and on the tested sample.
- Transfer limits: Factor-portfolio evidence does not directly determine eight-ETF results, but defeats universal claims.
- Frozen-universe relevance: Requires an unlevered cap, friction tests, and explicit rejection if validation is fragile.

## Campaign constraints

The four admitted families are fixed, long-only, unlevered rule sets with complete predeclared grids. The intended survivor is one fixed parameter tuple usable without annual or periodic retuning. Durability, neighboring-parameter stability, calendar and rolling-period consistency, friction robustness, and economic explainability precede fitted CAGR. A sustainable 15–20% or higher CAGR is aspirational, never a threshold.

The two counterevidence records prevent treating time-series momentum or volatility management as universal. Futures, long-short, leverage, reconstructed histories, factor portfolios, same-close fills, and total-return indices do not establish executable fills for this QFQ-normalized ETF simulation.

Rejected alternative: short-horizon reversal was not admitted because the bounded campaign lacks directly transferable support and the idea is expected to be materially friction-sensitive.
