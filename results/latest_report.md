# ETF Quant Research Report

Research-only historical evidence. Human and Independent Audit approval remain required.

Experiments: 4

## Provider-backed run status

- Status: `COMPLETED_RESEARCH_ONLY_NO_ACCEPTED_CANDIDATE`
- Moomoo/OpenD SDK: `10.10.7008`; quote-only preflight passed.
- Full configured download: 3 clean datasets and 13 rejected/quarantined datasets.
- Research universe: QQQ, TLT, IEF.
- TRAIN: 2010-01-01 through 2018-12-31.
- VALIDATION: 2019-01-01 through 2022-12-31.
- FINAL_HOLDOUT accessed: `false`.
- Search count: one candidate in each of four families; every family stopped on `ROBUSTNESS_DETERIORATED`.
- Validated snapshot: none; no candidate passed all deterministic gates.
- StrategyBase export: not generated.

## risk_managed_trend-0dc5fd8e9f17b21b-20260911T151548867625Z-2199bd86

Candidate: risk_managed_trend-0dc5fd8e9f17b21b
Candidate digest: a14e7798cc25a5e4cf4c8a577f8b8926b8d09f05fd9e82a11d0dbf431622d3ec
Family: risk_managed_trend
Parameters: {"maximum_exposure":0.25,"target_volatility":0.08,"trend_window":100,"volatility_window":20}
Score: 3.69045744
Train CAGR: 0.01202747093592893
Validation CAGR: 0.005521602036221429
Sharpe: 0.3191613650369698
Sortino: 0.4324350720471111
Calmar: 0.14006822336670205
Max drawdown: -0.03942080440162177
Buy-and-hold total return: 0.21539783878027507
Benchmark excess return: -0.1931740611830377
Cash total return: 0.0
Walk-forward consistency: 0.6666666666666666
Walk-forward fold returns: 1=0.018617129652500397, 2=0.029731807795766008, 3=-0.018646785216189343
Parameter stability: 1.0
Friction sensitivity: 0.0
Friction returns: 0bps=0.025878171980051157, 25bps=-0.004129123547712998, 3bps=0.0222239066503358, 50bps=-0.03314951634248953
Bootstrap median interval: [0.0, 0.0]
Accepted: False
Reason: MARKET_DATA_RESEARCH_ONLY; one or more gates failed
Stop reason: CANDIDATE_EVALUATED

## trend-a99a1e46cabcb494-20260911T151544559735Z-c2b1ad59

Candidate: trend-a99a1e46cabcb494
Candidate digest: 0af19fa0ad8bf1ff83f42c97ed3447b7a9a402d13e6dc27e897e31c26fcc2c02
Family: trend
Parameters: {"allocation":0.25,"fast_window":15,"slow_window":40}
Score: 3.47416115
Train CAGR: 0.008347143086748332
Validation CAGR: 0.005532726418425948
Sharpe: 0.31093474367724266
Sortino: 0.4255122946481756
Calmar: 0.12493330754512329
Max drawdown: -0.04428543938475049
Buy-and-hold total return: 0.21539783878027507
Benchmark excess return: -0.19312891667112408
Cash total return: 0.0
Walk-forward consistency: 0.6666666666666666
Walk-forward fold returns: 1=0.037087134180853853, 2=0.012902820726702346, 3=-0.02728057508287074
Parameter stability: 1.0
Friction sensitivity: 0.0
Friction returns: 0bps=0.02647115569475389, 25bps=-0.007963431875452565, 3bps=0.022268922025299842, 50bps=-0.04110529995906331
Bootstrap median interval: [0.0, 0.0]
Accepted: False
Reason: MARKET_DATA_RESEARCH_ONLY; one or more gates failed
Stop reason: CANDIDATE_EVALUATED

## momentum-0989605e3d57ad58-20260911T151545630861Z-686d2adf

Candidate: momentum-0989605e3d57ad58
Candidate digest: db3c35817b23048294775a57f8de9ddacc9a799555877d94d732238df5d5d505
Family: momentum
Parameters: {"allocation":0.25,"lookback":63}
Score: 2.74739181
Train CAGR: 0.014737290812157688
Validation CAGR: 0.005145832037847908
Sharpe: 0.2741258649071815
Sortino: 0.37430461061743914
Calmar: 0.11727487495266962
Max drawdown: -0.043878384350652166
Buy-and-hold total return: 0.21539783878027507
Benchmark excess return: -0.19469811810129212
Cash total return: 0.0
Walk-forward consistency: 0.6666666666666666
Walk-forward fold returns: 1=0.0390254946374744, 2=0.022364745154986432, 3=-0.03764705621524833
Parameter stability: 1.0
Friction sensitivity: 0.0
Friction returns: 0bps=0.023738234975767325, 25bps=-0.0012553261361757384, 3bps=0.020699722316654956, 50bps=-0.025520582477282727
Bootstrap median interval: [0.0, 0.0]
Accepted: False
Reason: MARKET_DATA_RESEARCH_ONLY; one or more gates failed
Stop reason: CANDIDATE_EVALUATED

## trend_momentum-4586449b6bd9be00-20260911T151547228371Z-9fd3f6a3

Candidate: trend_momentum-4586449b6bd9be00
Candidate digest: 177567c919a880207dbdeab01bc54cc204721d494d1e14d22334668fd1206d65
Family: trend_momentum
Parameters: {"allocation":0.25,"fast_window":15,"momentum_lookback":63,"slow_window":40}
Score: -1.6216156
Train CAGR: 0.007555775470630799
Validation CAGR: 0.0012085422755616637
Sharpe: 0.081536905949845
Sortino: 0.10868144520790542
Calmar: 0.028770371196310093
Max drawdown: -0.04200648880458879
Buy-and-hold total return: 0.21539783878027507
Benchmark excess return: -0.21056486759508464
Cash total return: 0.0
Walk-forward consistency: 0.6666666666666666
Walk-forward fold returns: 1=0.031836141656648165, 2=0.0010275990923795941, 3=-0.030616877741290183
Parameter stability: 1.0
Friction sensitivity: 0.0
Friction returns: 0bps=0.008548544712057238, 25bps=-0.02193254170312542, 3bps=0.00483297111103842, 50bps=-0.05134549133129218
Bootstrap median interval: [0.0, 0.0]
Accepted: False
Reason: MARKET_DATA_RESEARCH_ONLY; one or more gates failed
Stop reason: CANDIDATE_EVALUATED
