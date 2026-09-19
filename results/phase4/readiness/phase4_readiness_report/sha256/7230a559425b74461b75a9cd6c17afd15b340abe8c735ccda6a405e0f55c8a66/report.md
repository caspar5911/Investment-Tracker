# Phase 4 Readiness Audit

Status: PHASE_4_READY

## Bootstrap evidence

- Bootstrap statistic: median daily equal-weight portfolio return
- Sampling: independently with replacement from daily equal-weight portfolio returns
- Input derivation: percentage changes of the aggregate validation equity curve after dropping the first missing change
- Random generator: numpy.random.default_rng(0)
- Median statistic per resample
- 2,000 bootstrap draws
- PRNG seed: 0
- Interval endpoints: 5th and 95th percentiles using NumPy percentile defaults
- All 2,000 resampled medians were exactly zero
- Sample count: 1,007
- Sign counts: 288 negative, 368 zero, 351 positive
- Reproduced interval: [0.0, 0.0]
- Claim scope: MEDIAN_DAILY_EQUAL_WEIGHT_PORTFOLIO_RETURN_ONLY

## Search-aware boundaries

- 136 historical Phase 2 trials
- Phase 4 budget consumed: 0 of 3,000
- Maximum new strategy families: 10
- Maximum candidate trials per family: 500
- Maximum aggregate new candidate trials: 3,000
- DSR: UNKNOWN/NOT_IMPLEMENTED — Deflated Sharpe Ratio is not implemented for this readiness audit.
- PBO: UNKNOWN/NOT_IMPLEMENTED — Probability of Backtest Overfitting is not implemented for this readiness audit.

## Frozen temporal split

- Symbols: SPY, QQQ, IWM, TLT, IEF, GLD, VNQ, XLP
- TRAIN declared: 2014-01-02 through 2018-12-31; actual: 2014-01-02 through 2018-12-31 (1,258 sessions)
- VALIDATION declared: 2019-01-01 through 2022-12-30; actual: 2019-01-02 through 2022-12-30 (1,008 sessions)

## Methodology and safety

- QFQ is research-only normalized simulation.
- Signal series: QFQ
- Execution series: QFQ_NORMALIZED
- Decision grade: false
- Provider calls: 0
- External strategy research performed: false
- Strategy search executed: false
- Final holdout accessed: false
- Protected symbols accessed: []
- Live trading capability: false
- No strategy discovery was authorized.

## Evidence artifacts

- Pinned bootstrap source: `results/experiments/risk_managed_trend-ee8a71fb71e3d80f-20260911T194002253141Z-bcabf074.json`; content_sha256=`438dda42ceacece3c7d3b73512d9898017a4c180e1b368cdc7c6dee299f5d4b5`; envelope_sha256=`3e72fc05aa1c5d9e0ceca4a935ebb6672cd068d4bdf67b16c5d4fbbb121a797e`
- Phase 3 universe: `results/phase3/universes/de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76/manifest.json`; content_sha256=`de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76`; envelope_sha256=`2217e84065db40f8cb90480707a9dd0616914eb0ef370f6996ceb3dffa6c7142`
- Phase 3 DQ snapshot: `results/phase3/campaigns/PHASE3-ETF-DQ-2014-2022-20260912T0254Z/dq-snapshots/2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75.json`; content_sha256=`2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75`; envelope_sha256=`daa7699eb1a59d44f1af1363f28bd25e9df67d5c8d6044b2f015f7292ad30c42`
- Bootstrap input vector: `results/phase4/readiness/bootstrap_input_vector/sha256/9b4fca3088a63fe31009a105309fc2c8760fcb26c519b3a0856f2a6e5171f438/vector.json`; content_sha256=`9b4fca3088a63fe31009a105309fc2c8760fcb26c519b3a0856f2a6e5171f438`; envelope_sha256=`a4016312075cc223645d3062ca89c873c5a7ccbf01822ef0aecc0525429f3b68`
- Bootstrap audit: `results/phase4/readiness/bootstrap_audit/sha256/c9ab2680c68554acd90e672c294117dc6b576e357215244057b3c3c7bdb883f9/audit.json`; content_sha256=`c9ab2680c68554acd90e672c294117dc6b576e357215244057b3c3c7bdb883f9`; envelope_sha256=`d3003e7e4f88acc467b0d87fb0ca5821f06c2db4c6507d317b970ab655379c6e`
- Trial authority: `results/phase4/readiness/trial_authority/sha256/fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994/authority.json`; content_sha256=`fb88b52ceba1e53de0d3829a5dc995919bfec2711801700374bf25ce68cd7994`; envelope_sha256=`2ab77e480a61c57f1c29395d4e93c2d9302533ab2f67ce364037965d1e1eb3f3`
- Split manifest: `results/phase4/readiness/phase4_split_manifest/sha256/b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7/manifest.json`; content_sha256=`b273f79795237caca08d1a10388be8d300e9f4b5f51c818a24456c972c7bb4d7`; envelope_sha256=`3300510d6ea86aa077b5a2a2c2dd734d7e3602cc87513910af8db7c004fe0dab`
- Campaign configuration: `results/phase4/readiness/phase4_campaign_configuration/sha256/8fdd8f7f8125ca658942b97167bfce0d657b8a51440e99435a5b0c7322631b13/configuration.json`; content_sha256=`8fdd8f7f8125ca658942b97167bfce0d657b8a51440e99435a5b0c7322631b13`; envelope_sha256=`56d9f19e27ec541a853cd8e9dd116d4976c3e39f03b499f3e941bd64ccce0bdb`

## Protected historical trees

- `data/cache/phase3`: `66bc95073d534f6040e37cacf8d9e6b467d6b59e64ba4d045217d72441650c6d`
- `results/experiments`: `2d7a4b3942191e958085d32a9e475ad72b99c8d78185774c20278eb53c4d13a8`
- `results/phase3`: `bc44039c74eab8bbd3b238d0e8eadb25582047fd4b588d48c0ea9836e890fd65`
