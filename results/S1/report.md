# S1 — Malaysian SnR with confluences (GSE Strategy v4.0 research variants)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

10,368 combinations: 324 trade designs × 32 confluence combinations (d1, sweep, session, zone, mtf). Train 2016–2018 picks, validation 2019–2022 judges, test untouched. OANDA bid/ask + 0.10 slippage; conservative intrabar order.

Git `6c8c222a82` (dirty) · dataset `a8bd36567d0f…`

## Summary

- Combinations with ≥ 100 training trades: 701 of 10,368.
- Positive after costs: train 4, validation 0, both 0.
- Training rank vs validation rank (Spearman): 0.842. Near zero means training results do not carry over.
- Luck line: among 701 combinations with no edge, the best training SQN would reach about 3.6. Best training SQN found: 1.543.
- Finalists (top 20 training SQN), judged on validation: 20 rejected.

## The Pine strategy as written (15m, lookback 10, fresh, limit, with 4H, no filters)

| chart_tf | swing_len | level_type | entry_mode | h4_mode | stop_atr | d1 | sweep | session | zone | mtf | train_trades | train_expectancy_R | val_trades | val_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 10 | fresh | limit | with | 0.000 | False | False | False | False | False | 416 | -1.030 | 665 | -0.858 |

## Finalists on validation

| chart_tf | swing_len | level_type | entry_mode | h4_mode | stop_atr | d1 | sweep | session | zone | mtf | train_trades | train_expectancy_R | train_sqn | val_net_trades | val_net_expectancy_R | val_net_profit_factor | val_net_ci_low | val_years_positive | val_gross_expectancy_R | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 3 | fresh | limit | with | 3.000 | False | False | True | True | False | 176 | -0.044 | -0.424 | 239 | -0.043 | 0.938 | -0.279 | 2 | 0.013 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | False | False | True | False | False | 183 | -0.038 | -0.373 | 243 | -0.072 | 0.896 | -0.294 | 2 | -0.009 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | False | False | False | True | False | 268 | -0.025 | -0.300 | 395 | -0.092 | 0.868 | -0.284 | 2 | 0.021 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | False | False | False | False | False | 274 | -0.037 | -0.450 | 400 | -0.112 | 0.841 | -0.301 | 2 | 0.003 | rejected |
| 15m | 5 | both | limit | with | 3.000 | True | False | False | True | False | 110 | -0.085 | -0.656 | 141 | -0.129 | 0.818 | -0.408 | 2 | -0.002 | rejected |
| 15m | 3 | both | limit | with | 3.000 | False | False | False | True | False | 286 | -0.038 | -0.473 | 425 | -0.135 | 0.810 | -0.317 | 1 | -0.015 | rejected |
| 15m | 5 | both | limit | with | 3.000 | False | False | False | True | False | 263 | -0.027 | -0.315 | 418 | -0.142 | 0.803 | -0.327 | 0 | -0.005 | rejected |
| 15m | 10 | fresh | close_back | against | 3.000 | False | False | True | True | False | 102 | -0.074 | -0.515 | 119 | -0.146 | 0.801 | -0.497 | 1 | -0.021 | rejected |
| 15m | 5 | fresh | limit | with | 3.000 | True | False | False | True | False | 106 | -0.041 | -0.303 | 135 | -0.156 | 0.783 | -0.438 | 1 | 0.002 | rejected |
| 15m | 5 | fresh | limit | with | 3.000 | True | False | False | False | False | 108 | -0.059 | -0.446 | 135 | -0.156 | 0.782 | -0.438 | 1 | -0.004 | rejected |
| 15m | 5 | fresh | limit | with | 3.000 | False | False | False | False | False | 259 | -0.037 | -0.432 | 405 | -0.159 | 0.781 | -0.347 | 0 | -0.019 | rejected |
| 15m | 3 | both | limit | with | 3.000 | False | False | False | False | False | 327 | -0.034 | -0.448 | 496 | -0.162 | 0.776 | -0.330 | 1 | -0.054 | rejected |
| 15m | 5 | both | limit | with | 3.000 | False | False | False | False | False | 306 | -0.035 | -0.447 | 485 | -0.163 | 0.774 | -0.330 | 1 | -0.081 | rejected |
| 1H | 5 | both | limit | with | 1.500 | False | False | False | True | False | 112 | -0.105 | -0.721 | 215 | -0.178 | 0.769 | -0.439 | 0 | -0.023 | rejected |
| 15m | 5 | fresh | limit | with | 3.000 | False | False | False | True | False | 254 | -0.018 | -0.205 | 401 | -0.179 | 0.756 | -0.362 | 0 | -0.023 | rejected |
| 15m | 3 | both | limit | with | 3.000 | True | False | False | False | False | 141 | 0.154 | 1.296 | 199 | -0.233 | 0.687 | -0.520 | 0 | -0.098 | rejected |
| 15m | 5 | flip | close_back | with | 3.000 | False | False | False | False | False | 143 | -0.039 | -0.329 | 175 | -0.280 | 0.646 | -0.538 | 0 | -0.176 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | True | False | False | True | False | 115 | 0.202 | 1.543 | 154 | -0.285 | 0.626 | -0.548 | 0 | -0.099 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | True | False | False | False | False | 118 | 0.171 | 1.327 | 155 | -0.291 | 0.620 | -0.562 | 0 | -0.110 | rejected |
| 15m | 3 | both | limit | with | 3.000 | True | False | False | True | False | 123 | 0.140 | 1.122 | 169 | -0.291 | 0.621 | -0.552 | 0 | -0.110 | rejected |

## What each choice does on average (combinations with enough training trades)

### chart_tf

| chart_tf | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| 15m | 579.0 | -0.561 | -0.466 | -0.008 |
| 1H | 122.0 | -0.510 | -0.407 | -0.001 |

### swing_len

| swing_len | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| 3 | 300.0 | -0.570 | -0.472 | -0.027 |
| 5 | 242.0 | -0.529 | -0.440 | -0.001 |
| 10 | 159.0 | -0.554 | -0.447 | -0.008 |

### level_type

| level_type | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| both | 330.0 | -0.531 | -0.443 | -0.024 |
| flip | 110.0 | -0.747 | -0.575 | -0.008 |
| fresh | 261.0 | -0.498 | -0.421 | -0.001 |

### entry_mode

| entry_mode | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| close_back | 313.0 | -0.455 | -0.392 | -0.008 |
| limit | 368.0 | -0.634 | -0.505 | -0.001 |
| rejection | 20.0 | -0.579 | -0.533 | -0.300 |

### h4_mode

| h4_mode | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| against | 324.0 | -0.565 | -0.421 | -0.001 |
| with | 377.0 | -0.542 | -0.485 | -0.043 |

### stop_atr

| stop_atr | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| 0.000 | 346.0 | -0.809 | -0.652 | -0.066 |
| 1.500 | 241.0 | -0.361 | -0.293 | -0.001 |
| 3.000 | 114.0 | -0.179 | -0.203 | -0.008 |

### d1

| d1 | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| False | 512.0 | -0.522 | -0.437 | -0.001 |
| True | 189.0 | -0.635 | -0.505 | -0.066 |

### sweep

| sweep | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| False | 680.0 | -0.550 | -0.451 | -0.001 |
| True | 21.0 | -0.621 | -0.606 | -0.336 |

### session

| session | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| False | 410.0 | -0.537 | -0.459 | -0.001 |
| True | 291.0 | -0.574 | -0.450 | -0.027 |

### zone

| zone | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| False | 430.0 | -0.567 | -0.462 | -0.007 |
| True | 271.0 | -0.530 | -0.444 | -0.001 |

### mtf

| mtf | combinations | train_R | val_R | best_val_R |
|---|---|---|---|---|
| False | 693.0 | -0.548 | -0.451 | -0.001 |
| True | 8.000 | -0.954 | -0.837 | -0.329 |

## Conclusion

**No combination passes validation.** Training picked the most consistent combinations; none of them made money after costs on 2019–2022 with enough evidence. Tuning these rules and confluences does not produce a reliable edge on XAU/USD.

## Limitations

- Mechanical rules: discretionary judgement is not tested.
- No gap levels (GSE does not draw them; on gold intraday they are rare and tiny).
- Discount/premium uses the middle of the last swing range, not GSE's Golden Zone gate (tested in O1/T1).
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
