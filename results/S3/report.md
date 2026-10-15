# S3 — Fresh and flipped level touches with inducement, stops, targets and trailing (GSE v4.1 levels)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

86,184 combinations: 108 trade designs × 3 stops × 7 exits × 19 inducement settings × 2 session settings. Train 2016–2018 picks, validation 2019–2022 judges; the test period was spent on X1 and is not used. OANDA bid/ask + 0.10 slippage; conservative intrabar order. Rules: FRESH_FLIP_TOUCH_SPEC.md.

Git `e390e0e453` · dataset `7852581fbc17…`

## Summary

- Combinations with ≥ 100 training trades: 18,487 of 86,184.
- Positive after costs: train 95, validation 517, both 15.
- Training rank vs validation rank (Spearman): 0.639. Near zero means training results do not carry over.
- Luck line: among 18,487 combinations with no edge, the best training SQN would reach about 4.4. Best training SQN found: 1.330.
- Finalists (top 20 training SQN), judged on validation: 19 rejected, 1 watch.

## The spec's base rule (15m, lookback 10, fresh, limit, either side, 1 ATR stop, 1.5R, no filters)

| chart_tf | swing_len | level_type | entry_mode | h4_mode | stop_atr | exit | inducement | session | train_trades | train_expectancy_R | val_trades | val_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 10 | fresh | limit | off | 1.000 | 1.5R | off | False | 901 | -0.505 | 1411 | -0.408 |

## Finalists on validation

| chart_tf | swing_len | level_type | entry_mode | h4_mode | stop_atr | exit | inducement | session | train_trades | train_win_rate | train_expectancy_R | train_sqn | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_ci_low | val_years_positive | val_gross_expectancy_R | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1H | 3 | fresh | limit | with | 3.000 | 3R | none_2 | False | 115 | 0.278 | 0.087 | 0.519 | 162 | 0.253 | 0.005 | 1.006 | -0.368 | 2 | -0.018 | watch |
| 1H | 3 | fresh | limit | with | 3.000 | 2R | none_2 | False | 129 | 0.357 | 0.054 | 0.425 | 185 | 0.324 | -0.034 | 0.951 | -0.311 | 2 | -0.045 | rejected |
| 15m | 3 | fresh | close_back | with | 3.000 | 2R | present_3 | True | 101 | 0.406 | 0.140 | 0.942 | 141 | 0.340 | -0.043 | 0.939 | -0.368 | 2 | 0.066 | rejected |
| 1H | 3 | fresh | limit | with | 3.000 | 1.5R | none_2 | False | 144 | 0.424 | 0.051 | 0.487 | 200 | 0.385 | -0.043 | 0.930 | -0.265 | 2 | 0.007 | rejected |
| 1H | 5 | fresh | limit | with | 1.500 | 1.5R | none_3 | False | 104 | 0.471 | 0.166 | 1.330 | 132 | 0.379 | -0.065 | 0.898 | -0.360 | 2 | 0.120 | rejected |
| 1H | 3 | fresh | limit | with | 3.000 | 2R | none_5 | True | 123 | 0.358 | 0.057 | 0.439 | 172 | 0.314 | -0.065 | 0.906 | -0.340 | 2 | -0.001 | rejected |
| 1H | 3 | fresh | limit | with | 3.000 | 3R | none_5 | True | 104 | 0.288 | 0.126 | 0.710 | 155 | 0.232 | -0.079 | 0.898 | -0.467 | 1 | 0.012 | rejected |
| 1H | 5 | fresh | limit | with | 1.500 | be_2R | none_3 | False | 101 | 0.287 | 0.060 | 0.462 | 130 | 0.269 | -0.098 | 0.846 | -0.423 | 2 | 0.126 | rejected |
| 15m | 3 | flipped | limit | off | 3.000 | 3R | swept_2_10 | True | 101 | 0.277 | 0.090 | 0.501 | 139 | 0.230 | -0.099 | 0.874 | -0.474 | 1 | -0.067 | rejected |
| 15m | 3 | fresh | close_back | with | 3.000 | 1.5R | present_3 | True | 105 | 0.476 | 0.119 | 0.959 | 143 | 0.378 | -0.119 | 0.820 | -0.381 | 2 | -0.001 | rejected |
| 1H | 5 | fresh | limit | with | 1.500 | 1.5R | none_5 | False | 142 | 0.430 | 0.060 | 0.572 | 191 | 0.356 | -0.122 | 0.814 | -0.357 | 1 | 0.016 | rejected |
| 1H | 5 | fresh | limit | with | 1.500 | 1R | none_3 | False | 106 | 0.547 | 0.081 | 0.824 | 132 | 0.417 | -0.178 | 0.701 | -0.413 | 0 | -0.020 | rejected |
| 15m | 3 | flipped | limit | off | 3.000 | 3R | swept_2_10 | False | 125 | 0.288 | 0.133 | 0.813 | 190 | 0.211 | -0.178 | 0.780 | -0.463 | 1 | -0.108 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | be_2R | present_3 | True | 128 | 0.328 | 0.106 | 0.875 | 186 | 0.242 | -0.180 | 0.729 | -0.419 | 1 | -0.014 | rejected |
| 1H | 3 | fresh | limit | off | 3.000 | 3R | none_2 | False | 167 | 0.275 | 0.075 | 0.542 | 232 | 0.207 | -0.180 | 0.775 | -0.455 | 1 | -0.197 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 3R | present_3 | True | 124 | 0.274 | 0.081 | 0.502 | 175 | 0.206 | -0.185 | 0.770 | -0.493 | 1 | 0.023 | rejected |
| 15m | 3 | fresh | close_back | with | 3.000 | 3R | present_2 | True | 142 | 0.310 | 0.156 | 0.995 | 173 | 0.220 | -0.186 | 0.776 | -0.539 | 1 | -0.023 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 2R | present_3 | True | 128 | 0.359 | 0.068 | 0.529 | 183 | 0.273 | -0.187 | 0.745 | -0.441 | 1 | 0.022 | rejected |
| 1H | 3 | fresh | limit | off | 3.000 | 3R | none_3 | False | 171 | 0.275 | 0.073 | 0.534 | 249 | 0.201 | -0.204 | 0.747 | -0.461 | 1 | -0.167 | rejected |
| 15m | 3 | flipped | limit | off | 3.000 | 3R | swept_3_20 | False | 105 | 0.286 | 0.123 | 0.691 | 154 | 0.195 | -0.242 | 0.707 | -0.538 | 0 | -0.152 | rejected |

## Does inducement help? (each setting against no inducement, everything else equal)

R_change is the mean change in R per trade after costs; better_share the share of pairs it improved. Pairs need 30 trades on both sides in that period.

| inducement | train_pairs | train_R_change | train_better_share | val_pairs | val_R_change | val_better_share |
|---|---|---|---|---|---|---|
| present_2 | 2087.0 | -0.030 | 0.386 | 2212.0 | -0.010 | 0.476 |
| present_3 | 1727.0 | -0.036 | 0.378 | 2026.0 | -0.029 | 0.447 |
| present_5 | 1288.0 | -0.029 | 0.352 | 1510.0 | -0.059 | 0.345 |
| cleared_2 | 2505.0 | 0.015 | 0.518 | 2926.0 | 0.022 | 0.533 |
| cleared_3 | 2388.0 | 0.029 | 0.552 | 2724.0 | -0.003 | 0.475 |
| cleared_5 | 2062.0 | 0.018 | 0.495 | 2293.0 | -0.007 | 0.466 |
| none_2 | 2266.0 | 0.009 | 0.577 | 2592.0 | -0.007 | 0.478 |
| none_3 | 2679.0 | -0.009 | 0.513 | 2956.0 | 0.004 | 0.560 |
| none_5 | 3008.0 | -0.012 | 0.510 | 3318.0 | -0.000 | 0.539 |
| swept_2_5 | 2079.0 | -0.031 | 0.376 | 2297.0 | 0.018 | 0.521 |
| swept_2_10 | 2288.0 | -0.010 | 0.461 | 2577.0 | 0.001 | 0.482 |
| swept_2_20 | 2410.0 | -0.006 | 0.444 | 2741.0 | 0.007 | 0.483 |
| swept_3_5 | 1628.0 | -0.026 | 0.388 | 1969.0 | -0.018 | 0.427 |
| swept_3_10 | 2072.0 | -0.001 | 0.472 | 2274.0 | -0.006 | 0.441 |
| swept_3_20 | 2210.0 | 0.020 | 0.520 | 2479.0 | 0.005 | 0.438 |
| swept_5_5 | 1201.0 | -0.036 | 0.359 | 1564.0 | -0.037 | 0.380 |
| swept_5_10 | 1480.0 | -0.019 | 0.405 | 1867.0 | -0.018 | 0.429 |
| swept_5_20 | 1850.0 | 0.011 | 0.462 | 2087.0 | -0.016 | 0.417 |

## What each choice does on average (combinations with enough training trades)

### chart_tf

| chart_tf | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 15m | 15795.0 | -0.342 | -0.247 | 0.206 | 0.290 |
| 1H | 2604.0 | -0.246 | -0.135 | 0.375 | 0.312 |
| 4H | 88.0 | -0.208 | -0.111 | 0.169 | 0.309 |

### swing_len

| swing_len | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 3 | 7521.0 | -0.313 | -0.226 | 0.240 | 0.294 |
| 5 | 6384.0 | -0.326 | -0.217 | 0.375 | 0.297 |
| 10 | 4582.0 | -0.357 | -0.258 | 0.346 | 0.286 |

### level_type

| level_type | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| flipped | 3085.0 | -0.313 | -0.171 | 0.206 | 0.308 |
| fresh | 15402.0 | -0.331 | -0.243 | 0.375 | 0.290 |

### entry_mode

| entry_mode | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| close_back | 8371.0 | -0.332 | -0.236 | 0.375 | 0.312 |
| limit | 10116.0 | -0.326 | -0.227 | 0.194 | 0.278 |

### h4_mode

| h4_mode | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| against | 5205.0 | -0.358 | -0.236 | 0.375 | 0.292 |
| off | 8006.0 | -0.318 | -0.215 | 0.246 | 0.298 |
| with | 5276.0 | -0.315 | -0.251 | 0.122 | 0.288 |

### stop_atr

| stop_atr | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 1.000 | 6371.0 | -0.448 | -0.319 | 0.375 | 0.258 |
| 1.500 | 6263.0 | -0.344 | -0.237 | 0.367 | 0.289 |
| 3.000 | 5853.0 | -0.181 | -0.129 | 0.283 | 0.336 |

### exit

| exit | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 1.5R | 2659.0 | -0.312 | -0.234 | 0.157 | 0.335 |
| 1R | 2691.0 | -0.300 | -0.232 | 0.107 | 0.418 |
| 2R | 2633.0 | -0.328 | -0.238 | 0.181 | 0.279 |
| 3R | 2576.0 | -0.352 | -0.246 | 0.283 | 0.208 |
| be_2R | 2654.0 | -0.318 | -0.234 | 0.187 | 0.240 |
| trail_atr | 2643.0 | -0.337 | -0.222 | 0.311 | 0.299 |
| trail_swing | 2631.0 | -0.353 | -0.210 | 0.375 | 0.268 |

### inducement

| inducement | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| cleared_2 | 1086.0 | -0.318 | -0.231 | 0.127 | 0.296 |
| cleared_3 | 949.0 | -0.324 | -0.243 | 0.098 | 0.294 |
| cleared_5 | 791.0 | -0.353 | -0.249 | 0.012 | 0.290 |
| none_2 | 1172.0 | -0.285 | -0.207 | 0.171 | 0.297 |
| none_3 | 1418.0 | -0.294 | -0.188 | 0.206 | 0.302 |
| none_5 | 1733.0 | -0.295 | -0.188 | 0.246 | 0.303 |
| off | 2240.0 | -0.292 | -0.183 | 0.375 | 0.305 |
| present_2 | 807.0 | -0.372 | -0.239 | 0.080 | 0.290 |
| present_3 | 655.0 | -0.363 | -0.248 | 0.064 | 0.289 |
| present_5 | 451.0 | -0.436 | -0.293 | 0.004 | 0.274 |
| swept_2_10 | 977.0 | -0.321 | -0.242 | 0.102 | 0.292 |
| swept_2_20 | 1117.0 | -0.324 | -0.227 | 0.194 | 0.295 |
| swept_2_5 | 845.0 | -0.341 | -0.251 | 0.042 | 0.290 |
| swept_3_10 | 806.0 | -0.345 | -0.269 | 0.053 | 0.285 |
| swept_3_20 | 903.0 | -0.329 | -0.259 | 0.074 | 0.287 |
| swept_3_5 | 700.0 | -0.369 | -0.258 | 0.072 | 0.289 |
| swept_5_10 | 637.0 | -0.372 | -0.279 | 0.114 | 0.279 |
| swept_5_20 | 719.0 | -0.368 | -0.286 | 0.067 | 0.277 |
| swept_5_5 | 481.0 | -0.392 | -0.295 | 0.092 | 0.273 |

### session

| session | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 10469.0 | -0.326 | -0.232 | 0.346 | 0.293 |
| True | 8018.0 | -0.331 | -0.229 | 0.375 | 0.293 |

## Conclusion

**No combination passes validation.** Training picked the most consistent combinations; none of them made money after costs on 2019–2022 with enough evidence. Tuning these touch rules, inducement, stops, targets and trailing does not produce a reliable edge on XAU/USD.

## Limitations

- Mechanical rules: discretionary judgement is not tested.
- Inducement is one mechanical reading (minor wick swings in front of the level); others exist.
- Trailing stops move at candle closes only; partial exits are not tested.
- 4H charts give few trades; most 4H combinations fall below the training minimum.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
