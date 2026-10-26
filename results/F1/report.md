# F1 — Forward test: flipped-level touches against random levels

Candles from **2026-10-13** to **2026-10-26 07:30:00+00:00** (OANDA M15). Frozen rule: `results/F1/rule.json`. Primary: 15m, lookback 10, flipped levels; the verdict waits for 400 resolved touches.

Git `2b14df381f`

## Verdict: running

5 of 400 resolved primary touches: a running tally, not evidence yet.

## Running tally

win = 1 ATR away from the level before 1 ATR through it, within 32 candles; random = 3 random levels per touch on the same side and distance. diff = real − random with a 90% weekly-block bootstrap interval. cost_atr = one spread plus slippage in ATR (median); a 1:1 trade with a 1 ATR stop breaks even at win = 0.5 + cost_atr / 2.

| chart_tf | swing_len | type | touches | resolved | pending | win_real | win_random | win_diff | win_diff_low | win_diff_high | ret16_diff | cost_atr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 10 | fresh | 17 | 17 | 0 | 0.529 | 0.549 | -0.020 | -0.211 | 0.167 | 1.296 | 0.097 |
| 15m | 10 | flipped | 6 | 5 | 1 | 0.200 | 0.765 | -0.565 | -0.565 | 0.091 | -1.562 | 0.120 |
| 15m | 3 | fresh | 46 | 43 | 3 | 0.488 | 0.614 | -0.125 | -0.148 | -0.107 | 0.103 | 0.099 |
| 15m | 3 | flipped | 12 | 9 | 3 | 0.667 | 0.594 | 0.073 | -0.100 | 0.333 | -1.366 | 0.104 |
| 15m | 5 | fresh | 30 | 29 | 1 | 0.552 | 0.540 | 0.011 | -0.043 | 0.100 | 0.899 | 0.097 |
| 15m | 5 | flipped | 10 | 7 | 3 | 0.429 | 0.655 | -0.227 | -0.488 | 0.385 | -2.678 | 0.108 |
| 1H | 10 | fresh | 5 | 4 | 1 | 0.750 | 0.583 | 0.167 | 0.036 | 0.167 | 2.242 | 0.048 |

## For comparison: E1 (2016–2022), 15m lookback 10 flipped

Train: win 0.533 against 0.469 random (+0.065). Validation: 0.492 against 0.463 (+0.028).
