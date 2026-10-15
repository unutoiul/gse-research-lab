# F1 — Forward test: flipped-level touches against random levels

Candles from **2026-10-13** to **2026-10-15 11:45:00+00:00** (OANDA M15). Frozen rule: `results/F1/rule.json`. Primary: 15m, lookback 10, flipped levels; the verdict waits for 400 resolved touches.

Git `aac081a683`

## Verdict: running

2 of 400 resolved primary touches: a running tally, not evidence yet.

## Running tally

win = 1 ATR away from the level before 1 ATR through it, within 32 candles; random = 3 random levels per touch on the same side and distance. diff = real − random with a 90% weekly-block bootstrap interval. cost_atr = one spread plus slippage in ATR (median); a 1:1 trade with a 1 ATR stop breaks even at win = 0.5 + cost_atr / 2.

| chart_tf | swing_len | type | touches | resolved | pending | win_real | win_random | win_diff | win_diff_low | win_diff_high | ret16_diff | cost_atr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 10 | fresh | 5 | 4 | 1 | 0.500 | 0.286 | 0.214 | 0.214 | 0.214 | 5.219 | 0.114 |
| 15m | 10 | flipped | 2 | 2 | 0 | 0.000 | 0.600 | -0.600 | -0.600 | -0.600 | -1.227 | 0.120 |
| 15m | 3 | fresh | 8 | 7 | 1 | 0.429 | 0.476 | -0.048 | -0.048 | -0.048 | 2.942 | 0.104 |
| 15m | 3 | flipped | 3 | 3 | 0 | 0.667 | 0.500 | 0.167 | 0.167 | 0.167 | -4.893 | 0.120 |
| 15m | 5 | fresh | 7 | 6 | 1 | 0.500 | 0.368 | 0.132 | 0.132 | 0.132 | 2.079 | 0.101 |
| 15m | 5 | flipped | 3 | 3 | 0 | 0.333 | 0.625 | -0.292 | -0.292 | -0.292 | -4.996 | 0.120 |
| 1H | 10 | fresh | 2 | 0 | 2 | – | 0.000 | – | – | – | – | 0.072 |

## For comparison: E1 (2016–2022), 15m lookback 10 flipped

Train: win 0.533 against 0.469 random (+0.065). Validation: 0.492 against 0.463 (+0.028).
