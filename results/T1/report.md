# T1 — The Golden Zone entry by chart timeframe (15m, 1H, 4H)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

GSE v4.0 defaults on each chart's own candles; a candidate is the Golden Zone turning on at a close. Execution RXM-1 (next open at bid/ask, level-wick stop, first-obstacle target, 16 candles of that timeframe). Costs: **net** = OANDA bid/ask + 0.10 slippage; **half** = half spread + 0.05; **gross** = mid, no slippage. Train 2016–2018, validation 2019–2022; test untouched.

Git `2ba3440560` (dirty) · dataset `a637520850ec…`

## Results

`net_avg_spread_R` is the spread each trade pays, in R; `risk_atr_median` the stop distance in ATR of that timeframe.

|  | net_trades | net_trades_per_week | net_win_rate | net_expectancy_R | net_profit_factor | net_max_drawdown_R | net_avg_spread_R | risk_atr_median | half_expectancy_R | gross_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|
| 15m · train | 309.0 | 1.974 | 0.269 | -0.378 | 0.493 | 131.3 | 0.193 | 1.313 | -0.222 | -0.030 |
| 15m · validate | 374.0 | 1.792 | 0.246 | -0.413 | 0.460 | 154.6 | 0.182 | 1.274 | -0.268 | -0.127 |
| 1H · train | 57.0 | 0.364 | 0.474 | 0.241 | 1.473 | 7.857 | 0.108 | 1.246 | 0.317 | 0.401 |
| 1H · validate | 86.0 | 0.412 | 0.267 | -0.465 | 0.376 | 40.0 | 0.080 | 1.195 | -0.376 | -0.312 |
| 4H · train | 8.000 | 0.051 | 0.250 | -0.124 | 0.838 | 3.076 | 0.084 | 1.220 | 0.155 | 0.185 |
| 4H · validate | 19.0 | 0.091 | 0.263 | -0.243 | 0.652 | 8.445 | 0.042 | 1.087 | -0.226 | -0.209 |

## 15m validation (net) by higher-timeframe stratum (4H, 1H)

| 4H & 1H bias vs trade | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| aligned | 57.0 | 0.193 | -0.549 | -31.3 | 0.313 | 31.3 | 0.883 | 0.946 |
| neutral | 66.0 | 0.364 | -0.148 | -9.778 | 0.747 | 24.8 | 1.085 | 0.791 |
| opposed | 154.0 | 0.221 | -0.476 | -73.3 | 0.419 | 76.9 | 0.875 | 0.949 |
| partial | 97.0 | 0.237 | -0.412 | -40.0 | 0.470 | 40.2 | 1.004 | 0.921 |

## 1H validation (net) by higher-timeframe stratum (1D, 4H)

| 1D & 4H bias vs trade | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| aligned | 11.0 | 0.182 | -0.452 | -4.967 | 0.457 | 5.373 | 0.685 | 0.897 |
| neutral | 18.0 | 0.333 | -0.334 | -6.017 | 0.507 | 11.7 | 1.034 | 0.883 |
| opposed | 29.0 | 0.276 | -0.523 | -15.2 | 0.282 | 15.2 | 0.696 | 0.852 |
| partial | 28.0 | 0.250 | -0.494 | -13.8 | 0.359 | 13.8 | 0.992 | 0.893 |

## 4H validation (net) by higher-timeframe stratum (1W, 1D)

| 1W & 1D bias vs trade | trades | win_rate | expectancy_R | total_R | profit_factor | max_drawdown_R | avg_mfe_R | avg_mae_R |
|---|---|---|---|---|---|---|---|---|
| aligned | 3.000 | 0.000 | -1.010 | -3.029 | 0.000 | 3.029 | 0.288 | 1.010 |
| neutral | 6.000 | 0.333 | 0.218 | 1.310 | 1.420 | 3.120 | 1.581 | 0.837 |
| opposed | 7.000 | 0.143 | -0.589 | -4.124 | 0.324 | 4.124 | 0.917 | 0.952 |
| partial | 3.000 | 0.667 | 0.411 | 1.233 | 2.220 | 1.010 | 1.565 | 0.622 |

## Conclusion

Not profitable on any timeframe, after or before costs: the higher timeframes do not rescue the entry.

Fewer than 100 trades in a period on: 1H, 4H, so those results are weak evidence.

## Limitations

- One entry rule (Golden Zone on), one execution model (RXM-1), GSE defaults: no setting was tuned here.
- Higher-timeframe candles are built from OANDA M15 with TradingView's session anchors.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
