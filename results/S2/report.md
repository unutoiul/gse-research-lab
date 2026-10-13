# S2 — Short target, long stop (Malaysian SnR designs with confluences)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

41,472 combinations: 1296 trade designs × 32 confluence combinations (d1, sweep, session, zone, mtf). Train 2016–2018 picks, validation 2019–2022 judges, test untouched. OANDA bid/ask + 0.10 slippage; conservative intrabar order.

Git `da1e1baa7a` · dataset `7b841bd4e46a…`

## Summary

- Combinations with ≥ 100 training trades: 5,064 of 41,472.
- Positive after costs: train 117, validation 139, both 3.
- Training rank vs validation rank (Spearman): 0.589. Near zero means training results do not carry over.
- Luck line: among 5,064 combinations with no edge, the best training SQN would reach about 4.1. Best training SQN found: 2.252.
- Finalists (top 20 training SQN), judged on validation: 19 rejected, 1 watch.

## Finalists on validation

| chart_tf | swing_len | level_type | entry_mode | h4_mode | stop_atr | target_r | d1 | sweep | session | zone | mtf | train_trades | train_win_rate | train_expectancy_R | train_sqn | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_ci_low | val_years_positive | val_gross_expectancy_R | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 3 | both | limit | with | 5.000 | 1.000 | False | True | False | True | False | 103 | 0.612 | 0.220 | 2.252 | 143 | 0.503 | 0.002 | 1.004 | -0.231 | 2 | 0.039 | watch |
| 15m | 3 | both | limit | with | 5.000 | 0.750 | False | True | False | True | False | 106 | 0.651 | 0.139 | 1.678 | 149 | 0.570 | -0.008 | 0.981 | -0.208 | 2 | 0.005 | rejected |
| 15m | 3 | fresh | limit | with | 5.000 | 0.500 | False | True | False | False | False | 100 | 0.740 | 0.105 | 1.567 | 144 | 0.667 | -0.011 | 0.969 | -0.190 | 2 | 0.035 | rejected |
| 15m | 3 | fresh | limit | with | 5.000 | 0.500 | False | True | False | True | False | 100 | 0.740 | 0.105 | 1.566 | 144 | 0.667 | -0.011 | 0.969 | -0.190 | 2 | 0.032 | rejected |
| 15m | 3 | both | limit | with | 5.000 | 0.500 | False | True | False | True | False | 108 | 0.731 | 0.092 | 1.412 | 155 | 0.658 | -0.018 | 0.947 | -0.172 | 2 | 0.020 | rejected |
| 15m | 3 | fresh | limit | with | 5.000 | 0.750 | True | False | False | True | False | 321 | 0.604 | 0.050 | 1.021 | 403 | 0.556 | -0.032 | 0.928 | -0.171 | 1 | 0.030 | rejected |
| 1H | 3 | both | limit | against | 5.000 | 0.250 | False | False | True | True | False | 234 | 0.829 | 0.037 | 1.178 | 285 | 0.768 | -0.037 | 0.841 | -0.128 | 0 | -0.010 | rejected |
| 1H | 3 | fresh | limit | with | 5.000 | 0.500 | True | False | False | False | False | 116 | 0.707 | 0.060 | 0.938 | 134 | 0.634 | -0.048 | 0.871 | -0.218 | 1 | -0.007 | rejected |
| 1H | 3 | fresh | limit | with | 5.000 | 0.500 | True | False | False | True | False | 115 | 0.704 | 0.056 | 0.871 | 125 | 0.632 | -0.051 | 0.863 | -0.228 | 1 | -0.012 | rejected |
| 15m | 3 | both | limit | with | 5.000 | 1.000 | False | True | False | False | False | 137 | 0.540 | 0.075 | 0.870 | 184 | 0.478 | -0.053 | 0.900 | -0.254 | 2 | -0.020 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 1.000 | False | True | False | False | False | 102 | 0.588 | 0.164 | 1.649 | 144 | 0.479 | -0.054 | 0.899 | -0.289 | 2 | 0.030 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 1.000 | False | True | False | True | False | 102 | 0.588 | 0.164 | 1.649 | 144 | 0.479 | -0.054 | 0.899 | -0.289 | 2 | 0.024 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 0.750 | False | True | False | False | False | 104 | 0.644 | 0.116 | 1.380 | 145 | 0.545 | -0.058 | 0.876 | -0.281 | 2 | 0.080 | rejected |
| 15m | 3 | fresh | limit | with | 3.000 | 0.750 | False | True | False | True | False | 104 | 0.644 | 0.116 | 1.380 | 145 | 0.545 | -0.058 | 0.876 | -0.281 | 2 | 0.076 | rejected |
| 15m | 3 | fresh | limit | with | 5.000 | 0.750 | True | False | True | True | False | 254 | 0.614 | 0.068 | 1.259 | 287 | 0.537 | -0.064 | 0.864 | -0.209 | 1 | -0.008 | rejected |
| 1H | 10 | flip | limit | with | 5.000 | 0.500 | False | False | False | False | False | 119 | 0.706 | 0.065 | 1.031 | 152 | 0.618 | -0.072 | 0.812 | -0.218 | 1 | -0.033 | rejected |
| 15m | 3 | both | limit | with | 5.000 | 0.500 | False | True | True | False | False | 101 | 0.713 | 0.064 | 0.932 | 120 | 0.625 | -0.075 | 0.807 | -0.251 | 1 | -0.005 | rejected |
| 15m | 3 | both | limit | with | 3.000 | 0.750 | False | True | False | True | False | 112 | 0.625 | 0.082 | 0.999 | 156 | 0.526 | -0.085 | 0.822 | -0.264 | 2 | 0.053 | rejected |
| 15m | 3 | both | limit | with | 3.000 | 1.000 | False | True | False | True | False | 110 | 0.564 | 0.114 | 1.181 | 154 | 0.455 | -0.097 | 0.824 | -0.323 | 2 | 0.017 | rejected |
| 15m | 3 | fresh | close_back | with | 5.000 | 1.000 | False | False | True | True | False | 355 | 0.549 | 0.050 | 0.942 | 462 | 0.459 | -0.118 | 0.790 | -0.239 | 1 | -0.052 | rejected |

## What each choice does on average (combinations with enough training trades)

### chart_tf

| chart_tf | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 15m | 3689.0 | -0.177 | -0.145 | 0.155 | 0.576 |
| 1H | 1375.0 | -0.120 | -0.092 | 0.071 | 0.594 |

### swing_len

| swing_len | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 3 | 2262.0 | -0.155 | -0.134 | 0.052 | 0.579 |
| 5 | 1688.0 | -0.163 | -0.125 | 0.071 | 0.584 |
| 10 | 1114.0 | -0.173 | -0.134 | 0.155 | 0.578 |

### level_type

| level_type | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| both | 2209.0 | -0.161 | -0.132 | 0.155 | 0.579 |
| flip | 1125.0 | -0.143 | -0.113 | 0.071 | 0.593 |
| fresh | 1730.0 | -0.175 | -0.140 | 0.098 | 0.574 |

### entry_mode

| entry_mode | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| close_back | 2454.0 | -0.166 | -0.118 | 0.155 | 0.603 |
| limit | 2234.0 | -0.158 | -0.136 | 0.069 | 0.557 |
| rejection | 376.0 | -0.153 | -0.180 | -0.011 | 0.572 |

### h4_mode

| h4_mode | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| against | 2142.0 | -0.189 | -0.128 | 0.155 | 0.582 |
| with | 2922.0 | -0.142 | -0.133 | 0.053 | 0.579 |

### stop_atr

| stop_atr | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 1.500 | 1794.0 | -0.251 | -0.204 | 0.046 | 0.546 |
| 3.000 | 1708.0 | -0.136 | -0.109 | 0.069 | 0.590 |
| 5.000 | 1562.0 | -0.087 | -0.071 | 0.155 | 0.610 |

### target_r

| target_r | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| 0.250 | 1325.0 | -0.149 | -0.125 | 0.028 | 0.725 |
| 0.500 | 1285.0 | -0.159 | -0.129 | 0.054 | 0.608 |
| 0.750 | 1244.0 | -0.166 | -0.131 | 0.116 | 0.522 |
| 1.000 | 1210.0 | -0.175 | -0.138 | 0.155 | 0.454 |

### d1

| d1 | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 3579.0 | -0.156 | -0.135 | 0.071 | 0.576 |
| True | 1485.0 | -0.175 | -0.120 | 0.155 | 0.591 |

### sweep

| sweep | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 4734.0 | -0.160 | -0.127 | 0.155 | 0.582 |
| True | 330.0 | -0.189 | -0.188 | 0.002 | 0.563 |

### session

| session | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 2898.0 | -0.161 | -0.135 | 0.107 | 0.579 |
| True | 2166.0 | -0.162 | -0.125 | 0.155 | 0.582 |

### zone

| zone | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 3362.0 | -0.155 | -0.127 | 0.155 | 0.585 |
| True | 1702.0 | -0.176 | -0.138 | 0.052 | 0.572 |

### mtf

| mtf | combinations | train_R | val_R | best_val_R | val_win_rate |
|---|---|---|---|---|---|
| False | 4815.0 | -0.162 | -0.130 | 0.155 | 0.580 |
| True | 249.0 | -0.150 | -0.140 | 0.053 | 0.591 |

## Conclusion

**No combination passes validation.** Training picked the most consistent combinations; none of them made money after costs on 2019–2022 with enough evidence. Tuning these rules and confluences does not produce a reliable edge on XAU/USD.

## Limitations

- Mechanical rules: discretionary judgement is not tested.
- No gap levels (GSE does not draw them; on gold intraday they are rare and tiny).
- Discount/premium uses the middle of the last swing range, not GSE's Golden Zone gate (tested in O1/T1).
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
