# R001 — train period (2016-01-01 to 2019-01-01)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

Golden Zone turning on at a candle close; control C0 (Require Sweep off) versus V1 (on). Execution RXM-1 (next open, level-wick stop, first-obstacle target, 16 candles, bid/ask fills). Not GSE behaviour: a labelled research model.

Git `03825be233` · dataset SHA-256 `a637520850ec…` · 156.6 weeks

## Results by arm and slippage

Headline slippage 0.10 (fixed before validation). Expectancy and drawdown in R after spread and slippage.

| arm@slippage | trades | trades_per_week | win_rate | avg_win_R | avg_loss_R | expectancy_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R | median_planned_rr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C0@0.00 | 309.0 | 1.974 | 0.272 | 1.548 | -0.958 | -0.277 | 0.603 | 103.1 | 0.999 | 0.875 | 3.116 |
| C0@0.10 | 309.0 | 1.974 | 0.269 | 1.372 | -1.021 | -0.378 | 0.493 | 131.3 | 0.883 | 0.923 | 2.741 |
| C0@0.30 | 309.0 | 1.974 | 0.243 | 1.179 | -1.096 | -0.543 | 0.345 | 176.9 | 0.705 | 0.983 | 2.324 |
| V1@0.00 | 2.000 | 0.013 | 0.000 | – | -1.000 | -1.000 | 0.000 | 2.000 | 0.642 | 1.000 | 7.250 |
| V1@0.10 | 2.000 | 0.013 | 0.000 | – | -1.070 | -1.070 | 0.000 | 2.140 | 0.579 | 1.070 | 6.681 |
| V1@0.30 | 2.000 | 0.013 | 0.000 | – | -1.183 | -1.183 | 0.000 | 2.366 | 0.471 | 1.183 | 5.756 |

**V1 − C0 expectancy (slippage 0.10):** -0.691 R, 90% weekly bootstrap interval [-0.830, -0.557].

**Inconclusive:** an arm has fewer than 100 trades (C0 309, V1 2), so the decision rule cannot be applied.

## What V1 changes inside C0

K: C0 candidates whose BOS had a paired qualified sweep (V1 keeps them). R: those without (V1 removes them). E: candidates only V1 produces (a new swept BOS while C0's zone was already on).

|  | trades | win_rate | expectancy_R | profit_factor | max_drawdown_R |
|---|---|---|---|---|---|
| K (paired sweep, kept by V1) | 2.000 | 0.000 | -1.070 | 0.000 | 2.140 |
| R (no paired sweep, removed by V1) | 307.0 | 0.270 | -0.374 | 0.498 | 129.1 |
| E (V1 only) | 0.000 | – | – | – | 0.000 |

## By higher-timeframe stratum (C0)

|  | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| aligned | 60.0 | 0.300 | -0.317 | -19.0 | 0.546 | 26.1 | 0.942 | 0.882 |
| neutral | 52.0 | 0.269 | -0.356 | -18.5 | 0.522 | 21.1 | 0.921 | 0.941 |
| opposed | 104.0 | 0.221 | -0.442 | -46.0 | 0.460 | 55.3 | 0.772 | 0.956 |
| partial | 93.0 | 0.301 | -0.359 | -33.4 | 0.486 | 42.4 | 0.948 | 0.901 |

## By session (C0)

|  | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| ASIA | 72.0 | 0.319 | -0.280 | -20.2 | 0.599 | 29.4 | 0.948 | 0.922 |
| LDN | 93.0 | 0.237 | -0.403 | -37.5 | 0.500 | 43.1 | 1.056 | 0.961 |
| LDN-NY | 104.0 | 0.308 | -0.306 | -31.8 | 0.565 | 42.8 | 0.817 | 0.893 |
| NY | 32.0 | 0.125 | -0.707 | -22.6 | 0.157 | 22.6 | 0.518 | 0.940 |
| OFF | 8.000 | 0.250 | -0.604 | -4.830 | 0.129 | 5.499 | 0.593 | 0.804 |

## By direction (C0)

|  | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| long | 158.0 | 0.222 | -0.476 | -75.1 | 0.397 | 94.4 | 0.919 | 0.950 |
| short | 151.0 | 0.318 | -0.277 | -41.8 | 0.606 | 44.8 | 0.845 | 0.894 |

## By sweep source of the paired sweep (C0, K only)

|  | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| swing_high | 1.000 | 0.000 | -1.055 | -1.055 | 0.000 | 1.055 | 1.158 | 1.055 |
| swing_low | 1.000 | 0.000 | -1.084 | -1.084 | 0.000 | 1.084 | 0.000 | 1.084 |

## Rejection funnel (candles in the period, first failing Golden Zone condition)

|  | ('C0', 'rejected') | ('C0', 'share_of_candles') | ('V1', 'rejected') | ('V1', 'share_of_candles') |
|---|---|---|---|---|
| ('long', 'direction') | 35036.0 | 0.495 | 35036.0 | 0.495 |
| ('long', 'location') | 30623.0 | 0.433 | 30623.0 | 0.433 |
| ('long', 'bias') | 2082.0 | 0.029 | 2082.0 | 0.029 |
| ('long', 'recent_bos') | 2391.0 | 0.034 | 2391.0 | 0.034 |
| ('long', 'room') | 333.0 | 0.005 | 333.0 | 0.005 |
| ('long', 'sweep') | 0.000 | 0.000 | 315.0 | 0.004 |
| ('long', 'qualified') | 0.000 | 0.004 | 0.000 | 0.000 |
| ('short', 'direction') | 35745.0 | 0.505 | 35745.0 | 0.505 |
| ('short', 'location') | 30064.0 | 0.425 | 30064.0 | 0.425 |
| ('short', 'bias') | 2106.0 | 0.030 | 2106.0 | 0.030 |
| ('short', 'recent_bos') | 2298.0 | 0.032 | 2298.0 | 0.032 |
| ('short', 'room') | 266.0 | 0.004 | 266.0 | 0.004 |
| ('short', 'sweep') | 0.000 | 0.000 | 297.0 | 0.004 |
| ('short', 'qualified') | 0.000 | 0.004 | 0.000 | 0.000 |

## Limitations

- Provisional until the parity gate: pivot tie rule assumed, OANDA mid prices for structure, not BlackBull.
- RXM-1 is a research execution model. A candle that reaches both stop and target counts as a stop.
- Each candidate is scored independently, so overlapping trades are counted separately.
- Costs: OANDA bid/ask on every fill plus the slippage shown; no commission or financing.
