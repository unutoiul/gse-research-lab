# G1 — Broad search for a profitable XAU/USD rule, judged on an untouched holdout

4,836 rules over 10 families. Train 2016–2018 and validation 2019–2022 pick up to 10 finalists; the holdout 2012–2015 (never used by any study) judges them once. OANDA bid/ask + 0.1 slippage. Pre-registered: results/G1/rule.json.

Git `da46dbbfda`

## Summary

- Rules with enough trades in both periods: 3,309 of 4,836.
- Positive after costs in both periods: 265 (about 83 expected by chance alone).
- Finalists (positive and profit factor ≥ 1.1 in both): 10.
- Holdout verdicts: 9 fail, 1 weak.

## Finalists on the holdout (2012–2015)

| family | tf | params | side | session | d1 | exit | train_trades | train_expectancy_R | train_profit_factor | val_trades | val_expectancy_R | val_profit_factor | holdout_trades | holdout_expectancy_R | holdout_profit_factor | holdout_ci_low | holdout_years_positive | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| big_bar | 1H | {"k": 2.0, "fade": false} | long | False | True | s1.5_t1.5 | 192 | 0.201 | 1.382 | 276 | 0.168 | 1.312 | 152 | -0.194 | 0.717 | -0.447 | 1 | fail |
| big_bar | 1H | {"k": 3.0, "fade": false} | long | False | True | s2_time10 | 64 | 0.337 | 2.190 | 75 | 0.303 | 1.873 | 54 | -0.055 | 0.874 | -0.370 | 2 | fail |
| big_bar | 1H | {"k": 2.0, "fade": false} | long | False | True | s2_time10 | 170 | 0.137 | 1.393 | 238 | 0.149 | 1.382 | 141 | -0.174 | 0.691 | -0.398 | 1 | fail |
| big_bar | 1H | {"k": 2.0, "fade": false} | long | False | True | s2_t3 | 135 | 0.233 | 1.333 | 180 | 0.259 | 1.373 | 102 | -0.074 | 0.905 | -0.482 | 2 | fail |
| big_bar | 1H | {"k": 2.0, "fade": false} | long | True | True | s1.5_t1.5 | 158 | 0.145 | 1.264 | 228 | 0.164 | 1.303 | 129 | -0.203 | 0.706 | -0.439 | 1 | fail |
| big_bar | 1H | {"k": 3.0, "fade": false} | long | False | True | s1.5_t1.5 | 69 | 0.440 | 2.026 | 83 | 0.196 | 1.371 | 57 | -0.145 | 0.784 | -0.551 | 2 | fail |
| big_bar | 1H | {"k": 2.0, "fade": false} | long | True | True | s2_t3 | 115 | 0.241 | 1.345 | 158 | 0.258 | 1.373 | 92 | -0.016 | 0.980 | -0.456 | 2 | fail |
| big_bar | 1H | {"k": 3.0, "fade": false} | long | False | False | s2_time10 | 107 | 0.135 | 1.364 | 147 | 0.165 | 1.436 | 204 | 0.029 | 1.074 | -0.143 | 2 | weak |
| big_bar | 1H | {"k": 3.0, "fade": false} | long | False | False | s1.5_t1.5 | 115 | 0.184 | 1.345 | 161 | 0.124 | 1.223 | 218 | -0.016 | 0.974 | -0.235 | 2 | fail |
| ema_cross | 4H | {"f": 5, "s": 20} | both | False | False | s2_t3 | 76 | 0.363 | 1.547 | 111 | 0.217 | 1.308 | 124 | -0.102 | 0.869 | -0.461 | 1 | fail |

## By family (rules with enough trades)

| family | rules | train_R | val_R | best_val_R | positive_both |
|---|---|---|---|---|---|
| asian_breakout | 322.0 | -0.108 | -0.128 | 0.160 | 15.0 |
| big_bar | 433.0 | -0.113 | -0.090 | 0.417 | 67.0 |
| donchian | 414.0 | -0.033 | -0.010 | 0.428 | 84.0 |
| drift | 92.0 | -0.190 | -0.131 | -0.007 | 0.000 |
| ema_cross | 243.0 | -0.086 | -0.060 | 0.250 | 34.0 |
| gse_break | 282.0 | -0.103 | -0.037 | 0.391 | 32.0 |
| gse_sweep | 142.0 | -0.208 | -0.147 | 0.357 | 5.000 |
| ny_open | 168.0 | -0.158 | -0.122 | 0.072 | 0.000 |
| prev_day | 192.0 | -0.137 | -0.098 | 0.188 | 6.000 |
| rsi2 | 1021.0 | -0.139 | -0.102 | 0.265 | 22.0 |

## Conclusion

**No rule passes the untouched holdout.** Rules that made money in 2016–2022 did not keep doing so in 2012–2015.

## Limitations

- 2012–2015 OANDA data has more gaps than 2016+ (see results/data_quality).
- Market orders only; no limit entries, partial exits or position sizing.
