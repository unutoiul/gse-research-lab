# S4 — GSE's two setups, tested separately (1D + 4H trend, 1H context, 15m entry)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

Setup A: first touch of a fresh 15m level after a pullback against the 1D + 4H trend. Setup B: first touch of a confirmed 15m flipped level, continuing the trend. Four entry triggers, two structural stops, two targets: 32 variants, all shown. Train 2016–2018 picks one per setup; validation 2019–2022 judges it. OANDA bid/ask + 0.10 slippage (net); gross = mid prices, no slippage. Rules: gse_research/setups.py.

Git `3323b484da` · dataset `cf16b9de4d73…`

## Every variant

| setup | trigger | stop | target | train_net_trades | train_net_win_rate | train_net_expectancy_R | train_net_profit_factor | train_net_max_drawdown_R | train_gross_expectancy_R | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_max_drawdown_R | val_gross_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pullback | touch | structural | tp2 | 116 | 0.000 | -1.258 | 0.000 | 145.9 | 0.021 | 131 | 0.031 | -0.933 | 0.186 | 128.6 | -0.386 |
| A_pullback | touch | structural | 2R | 133 | 0.038 | -1.134 | 0.062 | 150.9 | -0.218 | 153 | 0.092 | -0.894 | 0.171 | 136.8 | -0.245 |
| A_pullback | touch | structural_floor | tp2 | 107 | 0.131 | -0.361 | 0.619 | 44.0 | -0.019 | 114 | 0.105 | -0.587 | 0.386 | 67.0 | -0.392 |
| A_pullback | touch | structural_floor | 2R | 128 | 0.164 | -0.581 | 0.361 | 77.3 | -0.174 | 147 | 0.231 | -0.359 | 0.563 | 55.6 | -0.177 |
| A_pullback | rejection | structural | tp2 | 8 | 0.000 | -1.195 | 0.000 | 9.559 | -1.079 | 5 | 0.000 | -1.097 | 0.000 | 5.485 | -0.992 |
| A_pullback | rejection | structural | 2R | 10 | 0.000 | -1.178 | 0.000 | 11.8 | -0.648 | 12 | 0.083 | -0.861 | 0.160 | 10.3 | -0.745 |
| A_pullback | rejection | structural_floor | tp2 | 8 | 0.000 | -1.195 | 0.000 | 9.559 | -1.079 | 5 | 0.000 | -1.097 | 0.000 | 5.485 | -0.992 |
| A_pullback | rejection | structural_floor | 2R | 10 | 0.000 | -1.177 | 0.000 | 11.8 | -0.649 | 12 | 0.083 | -0.861 | 0.160 | 10.3 | -0.745 |
| A_pullback | sweep_reclaim | structural | tp2 | 62 | 0.129 | -0.527 | 0.532 | 40.5 | -0.077 | 69 | 0.130 | -0.519 | 0.527 | 51.4 | -0.218 |
| A_pullback | sweep_reclaim | structural | 2R | 80 | 0.300 | -0.351 | 0.603 | 34.1 | 0.255 | 89 | 0.191 | -0.654 | 0.350 | 63.1 | -0.254 |
| A_pullback | sweep_reclaim | structural_floor | tp2 | 62 | 0.177 | -0.424 | 0.592 | 32.0 | -0.140 | 65 | 0.138 | -0.564 | 0.459 | 45.4 | -0.310 |
| A_pullback | sweep_reclaim | structural_floor | 2R | 80 | 0.275 | -0.396 | 0.562 | 37.9 | 0.058 | 87 | 0.230 | -0.486 | 0.470 | 46.0 | -0.178 |
| A_pullback | bos | structural | tp2 | 10 | 0.300 | -0.153 | 0.810 | 6.586 | 0.251 | 15 | 0.067 | -0.910 | 0.105 | 14.1 | -0.596 |
| A_pullback | bos | structural | 2R | 28 | 0.286 | -0.313 | 0.619 | 14.1 | 0.022 | 32 | 0.250 | -0.334 | 0.593 | 16.9 | -0.248 |
| A_pullback | bos | structural_floor | tp2 | 10 | 0.300 | -0.153 | 0.810 | 6.586 | 0.251 | 15 | 0.067 | -0.910 | 0.105 | 14.1 | -0.596 |
| A_pullback | bos | structural_floor | 2R | 28 | 0.286 | -0.313 | 0.619 | 14.1 | 0.022 | 32 | 0.250 | -0.334 | 0.593 | 16.9 | -0.248 |
| B_flip | touch | structural | tp2 | 37 | 0.081 | -0.852 | 0.211 | 31.5 | -0.401 | 35 | 0.086 | -0.804 | 0.236 | 29.7 | -0.153 |
| B_flip | touch | structural | 2R | 51 | 0.176 | -0.609 | 0.366 | 33.1 | 0.114 | 49 | 0.143 | -0.691 | 0.292 | 37.5 | -0.195 |
| B_flip | touch | structural_floor | tp2 | 23 | 0.174 | -0.437 | 0.499 | 11.9 | -0.315 | 28 | 0.143 | -0.522 | 0.427 | 14.6 | -0.278 |
| B_flip | touch | structural_floor | 2R | 50 | 0.280 | -0.207 | 0.730 | 15.2 | 0.283 | 49 | 0.245 | -0.311 | 0.612 | 19.1 | 0.071 |
| B_flip | rejection | structural | tp2 | 1 | 0.000 | -1.163 | 0.000 | 1.163 | -0.943 | 0 | – | – | – | 0.000 | – |
| B_flip | rejection | structural | 2R | 3 | 0.333 | -0.153 | 0.806 | 2.373 | -0.006 | 4 | 0.250 | -0.333 | 0.590 | 3.248 | -0.242 |
| B_flip | rejection | structural_floor | tp2 | 1 | 0.000 | -1.151 | 0.000 | 1.151 | -0.947 | 0 | – | – | – | 0.000 | – |
| B_flip | rejection | structural_floor | 2R | 3 | 0.333 | -0.149 | 0.811 | 2.360 | -0.007 | 4 | 0.250 | -0.333 | 0.590 | 3.248 | -0.242 |
| B_flip | sweep_reclaim | structural | tp2 | 16 | 0.125 | -0.954 | 0.181 | 15.3 | -0.308 | 12 | 0.000 | -1.292 | 0.000 | 15.5 | -0.983 |
| B_flip | sweep_reclaim | structural | 2R | 30 | 0.367 | -0.160 | 0.802 | 9.322 | 0.216 | 26 | 0.269 | -0.410 | 0.543 | 15.1 | -0.184 |
| B_flip | sweep_reclaim | structural_floor | tp2 | 14 | 0.214 | -0.458 | 0.532 | 6.549 | -0.237 | 12 | 0.083 | -0.817 | 0.253 | 9.801 | -0.200 |
| B_flip | sweep_reclaim | structural_floor | 2R | 30 | 0.400 | 0.006 | 1.009 | 9.275 | 0.306 | 25 | 0.280 | -0.326 | 0.616 | 12.6 | 0.257 |
| B_flip | bos | structural | tp2 | 2 | 0.500 | 0.131 | 1.233 | 1.122 | 0.273 | 2 | 0.000 | -1.096 | 0.000 | 2.191 | -1.012 |
| B_flip | bos | structural | 2R | 10 | 0.300 | -0.194 | 0.748 | 5.514 | -0.087 | 11 | 0.182 | -0.562 | 0.384 | 8.100 | -0.454 |
| B_flip | bos | structural_floor | tp2 | 2 | 0.500 | 0.131 | 1.233 | 1.122 | 0.273 | 2 | 0.000 | -1.096 | 0.000 | 2.191 | -1.012 |
| B_flip | bos | structural_floor | 2R | 10 | 0.300 | -0.194 | 0.748 | 5.514 | -0.087 | 11 | 0.182 | -0.562 | 0.384 | 8.100 | -0.454 |

## Selected on train, judged on validation

| setup | trigger | stop | target | train_net_trades | train_net_expectancy_R | train_net_sqn | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_ci_low | val_gross_expectancy_R | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_flip | touch | structural_floor | 2R | 50 | -0.207 | -1.052 | 49 | 0.245 | -0.311 | 0.612 | -0.672 | 0.071 | inconclusive |
| A_pullback | sweep_reclaim | structural_floor | tp2 | 62 | -0.424 | -1.737 | 65 | 0.138 | -0.564 | 0.459 | -0.941 | -0.310 | rejected |

## Monte Carlo

Random entries: 50 runs with the same number of entries at random 15m closes in the trend's direction, with stop and target sizes drawn from the real trades. share_random_at_least_real is the share of random runs that did as well as the setup (small = the entries carry information). Trade resampling: one year of the real trades redrawn 5,000 times (yearly R, losing-year chance, drawdowns in R).

| setup | period | real_avg_R | random_avg_R_mean | random_p5 | random_p95 | share_random_at_least_real | trades_per_year | year_R_median | year_R_p5 | year_R_p95 | losing_year_chance | max_drawdown_R_median | max_drawdown_R_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_flip | train | -0.207 | -0.417 | -0.790 | -0.106 | 0.080 | 17 | -2.891 | -12.1 | 6.414 | 0.661 | 7.322 | 13.6 |
| B_flip | val | -0.311 | -0.375 | -0.627 | -0.111 | 0.400 | 12 | -3.574 | -9.792 | 2.719 | 0.854 | 6.491 | 11.6 |
| A_pullback | train | -0.424 | -0.378 | -0.722 | -0.098 | 0.560 | 21 | -9.702 | -21.8 | 5.923 | 0.848 | 13.9 | 22.9 |
| A_pullback | val | -0.564 | -0.401 | -0.798 | -0.115 | 0.800 | 16 | -9.748 | -19.3 | 2.634 | 0.900 | 12.4 | 19.3 |

## B_flip (touch, structural_floor, 2R): where it does better or worse

Net R per trade. Measured on both periods; nothing here was used to pick the variant.

### train

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2016 | 21.0 | 0.286 | -0.173 | -3.626 |
| 2017 | 5.000 | 0.200 | -0.464 | -2.318 |
| 2018 | 24.0 | 0.292 | -0.183 | -4.388 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 18.0 | 0.278 | -0.231 | -4.153 |
| London | 12.0 | 0.250 | -0.298 | -3.576 |
| New York | 20.0 | 0.300 | -0.130 | -2.604 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 21.0 | 0.286 | -0.173 | -3.626 |
| low | 17.0 | 0.294 | -0.179 | -3.035 |
| normal | 12.0 | 0.250 | -0.306 | -3.671 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 26.0 | 0.269 | -0.234 | -6.077 |
| contradict | 6.000 | 0.333 | -0.052 | -0.310 |
| neutral | 18.0 | 0.278 | -0.219 | -3.946 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| neutral | 19.0 | 0.316 | -0.110 | -2.099 |
| with trend | 31.0 | 0.258 | -0.266 | -8.234 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 31.0 | -0.266 | 19.0 | -0.110 | -0.155 |
| recent_bos | 17.0 | -0.528 | 33.0 | -0.041 | -0.486 |
| room | 23.0 | -0.525 | 27.0 | 0.064 | -0.589 |
| sweep_recent | 0.000 | – | 50.0 | -0.207 | – |
| rejection_recent | 15.0 | -0.459 | 35.0 | -0.098 | -0.361 |
| volume | 47.0 | -0.217 | 3.000 | -0.039 | -0.178 |
| killzone | 32.0 | -0.193 | 18.0 | -0.231 | 0.038 |
| score_75 | 5.000 | -1.062 | 45.0 | -0.112 | -0.950 |

### val

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2019 | 8.000 | 0.125 | -0.711 | -5.685 |
| 2020 | 15.0 | 0.067 | -0.840 | -12.6 |
| 2021 | 9.000 | 0.444 | 0.289 | 2.604 |
| 2022 | 17.0 | 0.353 | 0.027 | 0.463 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 12.0 | 0.083 | -0.812 | -9.741 |
| London | 16.0 | 0.188 | -0.494 | -7.896 |
| New York | 21.0 | 0.381 | 0.115 | 2.413 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 38.0 | 0.289 | -0.168 | -6.365 |
| low | 5.000 | 0.000 | -1.111 | -5.554 |
| normal | 6.000 | 0.167 | -0.551 | -3.305 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 27.0 | 0.296 | -0.149 | -4.031 |
| contradict | 5.000 | 0.000 | -1.055 | -5.273 |
| neutral | 17.0 | 0.235 | -0.348 | -5.920 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 2.000 | 0.000 | -1.067 | -2.133 |
| neutral | 19.0 | 0.158 | -0.568 | -10.8 |
| with trend | 28.0 | 0.321 | -0.082 | -2.298 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 28.0 | -0.082 | 21.0 | -0.616 | 0.533 |
| recent_bos | 15.0 | -0.442 | 34.0 | -0.253 | -0.189 |
| room | 28.0 | -0.517 | 21.0 | -0.035 | -0.482 |
| sweep_recent | 0.000 | – | 49.0 | -0.311 | – |
| rejection_recent | 13.0 | -0.118 | 36.0 | -0.380 | 0.263 |
| volume | 43.0 | -0.275 | 6.000 | -0.563 | 0.288 |
| killzone | 37.0 | -0.148 | 12.0 | -0.812 | 0.664 |
| score_75 | 4.000 | -0.295 | 45.0 | -0.312 | 0.017 |

## A_pullback (sweep_reclaim, structural_floor, tp2): where it does better or worse

Net R per trade. Measured on both periods; nothing here was used to pick the variant.

### train

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2016 | 15.0 | 0.200 | 0.023 | 0.342 |
| 2017 | 9.000 | 0.000 | -1.257 | -11.3 |
| 2018 | 38.0 | 0.211 | -0.404 | -15.4 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 24.0 | 0.125 | -0.776 | -18.6 |
| London | 11.0 | 0.091 | -0.972 | -10.7 |
| New York | 27.0 | 0.259 | 0.111 | 3.005 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 15.0 | 0.200 | 0.007 | 0.107 |
| low | 31.0 | 0.226 | -0.394 | -12.2 |
| normal | 16.0 | 0.062 | -0.888 | -14.2 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 26.0 | 0.115 | -0.750 | -19.5 |
| contradict | 13.0 | 0.231 | -0.053 | -0.688 |
| neutral | 23.0 | 0.217 | -0.267 | -6.140 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 17.0 | 0.118 | -0.670 | -11.4 |
| neutral | 28.0 | 0.250 | -0.181 | -5.080 |
| with trend | 17.0 | 0.118 | -0.580 | -9.852 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 17.0 | -0.580 | 45.0 | -0.366 | -0.214 |
| recent_bos | 0.000 | – | 62.0 | -0.424 | – |
| room | 52.0 | -0.442 | 10.0 | -0.335 | -0.107 |
| sweep_recent | 7.000 | -0.637 | 55.0 | -0.397 | -0.240 |
| rejection_recent | 27.0 | -0.769 | 35.0 | -0.159 | -0.610 |
| volume | 41.0 | -0.060 | 21.0 | -1.137 | 1.078 |
| killzone | 38.0 | -0.202 | 24.0 | -0.776 | 0.574 |
| score_75 | 0.000 | – | 62.0 | -0.424 | – |

### val

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2019 | 21.0 | 0.190 | -0.558 | -11.7 |
| 2020 | 15.0 | 0.067 | -0.874 | -13.1 |
| 2021 | 13.0 | 0.000 | -1.153 | -15.0 |
| 2022 | 16.0 | 0.250 | 0.195 | 3.128 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 23.0 | 0.130 | -0.467 | -10.7 |
| London | 17.0 | 0.176 | -0.563 | -9.578 |
| New York | 25.0 | 0.120 | -0.655 | -16.4 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 41.0 | 0.098 | -0.676 | -27.7 |
| low | 16.0 | 0.250 | -0.362 | -5.798 |
| normal | 8.000 | 0.125 | -0.396 | -3.167 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 23.0 | 0.217 | -0.279 | -6.419 |
| contradict | 21.0 | 0.095 | -0.722 | -15.2 |
| neutral | 21.0 | 0.095 | -0.719 | -15.1 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 29.0 | 0.069 | -0.907 | -26.3 |
| neutral | 22.0 | 0.136 | -0.697 | -15.3 |
| with trend | 14.0 | 0.286 | 0.354 | 4.951 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 14.0 | 0.354 | 51.0 | -0.816 | 1.170 |
| recent_bos | 2.000 | -1.150 | 63.0 | -0.546 | -0.604 |
| room | 63.0 | -0.545 | 2.000 | -1.184 | 0.640 |
| sweep_recent | 6.000 | 0.898 | 59.0 | -0.713 | 1.611 |
| rejection_recent | 28.0 | -0.627 | 37.0 | -0.517 | -0.110 |
| volume | 42.0 | -0.530 | 23.0 | -0.628 | 0.098 |
| killzone | 42.0 | -0.618 | 23.0 | -0.467 | -0.151 |
| score_75 | 1.000 | -1.073 | 64.0 | -0.556 | -0.516 |

## Conclusion

**Neither setup passes validation.** The variant training picked for each setup did not make money after costs on 2019–2022 with enough evidence.

## Limitations

- Trend from GSE's bias on 1D and 4H; other trend definitions could differ.
- One trade at a time per variant; a trade open blocks later signals.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
