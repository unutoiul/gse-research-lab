# E1 — Do GSE's levels have an edge? (first touches against random levels, before costs)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

Every first touch of a fresh level, and every first touch of a confirmed flipped level after its retest (GSE v4.1 levels), against random levels at the same distance from price on the same side. **win** = price reaches 1 ATR away from the level before 1 ATR through it, within 32 candles (no answer in that time is left out); **ret16** = the move 16 candles later, in ATR, in the level's direction. Random walk with no edge: win ≈ 0.5 and ret16 ≈ 0. diff = real − random, with a weekly-block bootstrap interval (90%, widened for 18 cells). Train 2016–2018 and validation 2019–2022; the test period is not used.

Git `a4212a9a33` · dataset `a637520850ec…`

## Verdict per cell

An **edge** needs the win-rate difference above zero, interval included, in both periods. The last three columns translate validation into a 1:1 trade at the level with a 1 ATR stop: gross R = 2 × win − 1, cost = one spread plus slippage in ATR (median), net = gross − cost.

| chart_tf | swing_len | type | verdict | train_win_diff | val_win_diff | val_win_diff_low | val_ret16_diff | val_gross_R_1to1 | val_cost_R_1to1 | val_net_R_1to1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 3 | fresh | no edge | 0.000 | 0.005 | -0.016 | -0.051 | -0.064 | 0.325 | -0.389 |
| 15m | 3 | flipped | weak sign | 0.026 | 0.025 | -0.018 | -0.185 | -0.020 | 0.297 | -0.317 |
| 15m | 5 | fresh | no edge | -0.024 | 0.001 | -0.027 | -0.062 | -0.088 | 0.326 | -0.414 |
| 15m | 5 | flipped | weak sign | 0.025 | 0.019 | -0.031 | 0.016 | -0.020 | 0.297 | -0.317 |
| 15m | 10 | fresh | no edge | -0.019 | -0.015 | -0.051 | -0.030 | -0.132 | 0.322 | -0.454 |
| 15m | 10 | flipped | weak sign | 0.065 | 0.028 | -0.043 | 0.050 | -0.017 | 0.284 | -0.301 |
| 1H | 3 | fresh | weak sign | 0.003 | 0.014 | -0.034 | 0.244 | -0.097 | 0.140 | -0.237 |
| 1H | 3 | flipped | no edge | -0.057 | 0.001 | -0.098 | -0.128 | -0.081 | 0.141 | -0.222 |
| 1H | 5 | fresh | weak sign | 0.013 | 0.001 | -0.054 | 0.108 | -0.095 | 0.140 | -0.235 |
| 1H | 5 | flipped | no edge | -0.010 | -0.004 | -0.116 | -0.169 | -0.030 | 0.144 | -0.174 |
| 1H | 10 | fresh | no edge | 0.023 | -0.023 | -0.095 | 0.221 | -0.169 | 0.139 | -0.308 |
| 1H | 10 | flipped | weak sign | 0.069 | 0.034 | -0.126 | 0.458 | 0.025 | 0.148 | -0.123 |
| 4H | 3 | fresh | no edge | -0.013 | 0.010 | -0.071 | -0.127 | -0.090 | 0.069 | -0.159 |
| 4H | 3 | flipped | no edge | 0.043 | -0.004 | -0.179 | -0.320 | -0.186 | 0.069 | -0.255 |
| 4H | 5 | fresh | no edge | -0.054 | 0.056 | -0.046 | 0.250 | -0.043 | 0.070 | -0.114 |
| 4H | 5 | flipped | no edge | 0.054 | -0.021 | -0.218 | -0.507 | -0.091 | 0.068 | -0.159 |
| 4H | 10 | fresh | no edge | -0.065 | 0.057 | -0.083 | -0.051 | 0.000 | 0.070 | -0.070 |
| 4H | 10 | flipped | no edge | -0.091 | 0.065 | -0.246 | 0.051 | 0.097 | 0.063 | 0.034 |

Cells: 12 no edge, 6 weak sign.

## Real against random, by period

| chart_tf | swing_len | type | period | touches | win_real | win_random | win_diff | win_diff_low | win_diff_high | ret16_real | ret16_random | ret16_diff | ret16_diff_low | cost_atr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 3 | fresh | train | 4267 | 0.471 | 0.471 | 0.000 | -0.026 | 0.023 | -0.017 | 0.082 | -0.099 | -0.270 | 0.425 |
| 15m | 3 | flipped | train | 1049 | 0.510 | 0.485 | 0.026 | -0.025 | 0.076 | -0.090 | 0.002 | -0.092 | -0.506 | 0.412 |
| 15m | 3 | fresh | val | 5888 | 0.468 | 0.463 | 0.005 | -0.016 | 0.027 | -0.007 | 0.044 | -0.051 | -0.195 | 0.325 |
| 15m | 3 | flipped | val | 1372 | 0.490 | 0.465 | 0.025 | -0.018 | 0.071 | -0.112 | 0.072 | -0.185 | -0.506 | 0.297 |
| 15m | 5 | fresh | train | 2646 | 0.449 | 0.473 | -0.024 | -0.057 | 0.006 | -0.103 | 0.087 | -0.190 | -0.411 | 0.425 |
| 15m | 5 | flipped | train | 765 | 0.509 | 0.484 | 0.025 | -0.035 | 0.087 | -0.048 | -0.002 | -0.046 | -0.516 | 0.406 |
| 15m | 5 | flipped | val | 953 | 0.490 | 0.471 | 0.019 | -0.031 | 0.076 | -0.015 | -0.032 | 0.016 | -0.386 | 0.297 |
| 15m | 5 | fresh | val | 3747 | 0.456 | 0.455 | 0.001 | -0.027 | 0.028 | -0.032 | 0.031 | -0.062 | -0.228 | 0.326 |
| 15m | 10 | fresh | train | 1311 | 0.438 | 0.457 | -0.019 | -0.059 | 0.022 | -0.088 | -0.008 | -0.080 | -0.370 | 0.428 |
| 15m | 10 | flipped | train | 449 | 0.533 | 0.469 | 0.065 | -0.009 | 0.134 | -0.185 | -0.113 | -0.072 | -0.691 | 0.386 |
| 15m | 10 | fresh | val | 1928 | 0.434 | 0.449 | -0.015 | -0.051 | 0.022 | -0.111 | -0.081 | -0.030 | -0.337 | 0.322 |
| 15m | 10 | flipped | val | 539 | 0.492 | 0.463 | 0.028 | -0.043 | 0.098 | 0.046 | -0.004 | 0.050 | -0.508 | 0.284 |
| 1H | 3 | fresh | train | 924 | 0.452 | 0.450 | 0.003 | -0.050 | 0.055 | 0.024 | -0.065 | 0.090 | -0.220 | 0.207 |
| 1H | 3 | flipped | train | 250 | 0.432 | 0.489 | -0.057 | -0.162 | 0.044 | -0.394 | 0.070 | -0.464 | -1.101 | 0.195 |
| 1H | 3 | flipped | val | 358 | 0.459 | 0.458 | 0.001 | -0.098 | 0.101 | -0.200 | -0.072 | -0.128 | -0.773 | 0.141 |
| 1H | 3 | fresh | val | 1296 | 0.451 | 0.437 | 0.014 | -0.034 | 0.062 | 0.004 | -0.240 | 0.244 | -0.049 | 0.140 |
| 1H | 5 | fresh | train | 573 | 0.455 | 0.443 | 0.013 | -0.052 | 0.078 | -0.037 | -0.167 | 0.131 | -0.241 | 0.207 |
| 1H | 5 | flipped | train | 160 | 0.462 | 0.473 | -0.010 | -0.145 | 0.123 | -0.207 | 0.001 | -0.208 | -1.076 | 0.195 |
| 1H | 5 | fresh | val | 802 | 0.452 | 0.451 | 0.001 | -0.054 | 0.057 | -0.030 | -0.138 | 0.108 | -0.328 | 0.140 |
| 1H | 5 | flipped | val | 232 | 0.485 | 0.489 | -0.004 | -0.116 | 0.110 | -0.089 | 0.080 | -0.169 | -0.881 | 0.144 |
| 1H | 10 | fresh | train | 315 | 0.457 | 0.434 | 0.023 | -0.059 | 0.105 | -0.084 | -0.205 | 0.121 | -0.381 | 0.211 |
| 1H | 10 | flipped | train | 95 | 0.516 | 0.447 | 0.069 | -0.117 | 0.250 | -0.018 | 0.144 | -0.162 | -1.300 | 0.198 |
| 1H | 10 | fresh | val | 427 | 0.415 | 0.438 | -0.023 | -0.095 | 0.048 | 0.128 | -0.093 | 0.221 | -0.392 | 0.139 |
| 1H | 10 | flipped | val | 121 | 0.512 | 0.478 | 0.034 | -0.126 | 0.184 | 0.315 | -0.144 | 0.458 | -0.620 | 0.148 |
| 4H | 3 | fresh | train | 257 | 0.451 | 0.464 | -0.013 | -0.108 | 0.080 | -0.081 | -0.158 | 0.076 | -0.539 | 0.106 |
| 4H | 3 | flipped | train | 62 | 0.500 | 0.457 | 0.043 | -0.180 | 0.255 | 0.502 | 0.002 | 0.500 | -0.666 | 0.106 |
| 4H | 3 | fresh | val | 345 | 0.455 | 0.445 | 0.010 | -0.071 | 0.093 | -0.143 | -0.016 | -0.127 | -0.654 | 0.069 |
| 4H | 3 | flipped | val | 86 | 0.407 | 0.411 | -0.004 | -0.179 | 0.171 | -0.459 | -0.139 | -0.320 | -1.337 | 0.069 |
| 4H | 5 | fresh | train | 167 | 0.413 | 0.467 | -0.054 | -0.176 | 0.065 | -0.174 | -0.166 | -0.009 | -0.609 | 0.106 |
| 4H | 5 | flipped | train | 43 | 0.535 | 0.481 | 0.054 | -0.203 | 0.323 | 0.494 | 0.155 | 0.339 | -1.219 | 0.112 |
| 4H | 5 | fresh | val | 207 | 0.478 | 0.422 | 0.056 | -0.046 | 0.162 | -0.044 | -0.294 | 0.250 | -0.447 | 0.070 |
| 4H | 5 | flipped | val | 55 | 0.455 | 0.476 | -0.021 | -0.218 | 0.210 | -0.294 | 0.213 | -0.507 | -1.599 | 0.068 |
| 4H | 10 | fresh | train | 77 | 0.416 | 0.481 | -0.065 | -0.237 | 0.101 | 0.036 | -0.040 | 0.076 | -1.080 | 0.106 |
| 4H | 10 | flipped | train | 22 | 0.500 | 0.591 | -0.091 | -0.428 | 0.253 | 0.661 | 0.960 | -0.299 | -1.841 | 0.112 |
| 4H | 10 | fresh | val | 118 | 0.500 | 0.443 | 0.057 | -0.083 | 0.192 | 0.065 | 0.116 | -0.051 | -1.097 | 0.070 |
| 4H | 10 | flipped | val | 31 | 0.548 | 0.484 | 0.065 | -0.246 | 0.383 | -0.001 | -0.052 | 0.051 | -1.822 | 0.063 |

## Inducement at lookback 10 (win rate by what lay in front of the level)

| chart_tf | type | period | inducement | touches | win_real | win_random | win_diff |
|---|---|---|---|---|---|---|---|
| 15m | fresh | train | none | 197 | 0.477 | 0.457 | 0.020 |
| 15m | fresh | train | present | 439 | 0.390 | 0.457 | -0.067 |
| 15m | fresh | train | cleared | 675 | 0.458 | 0.457 | 0.002 |
| 15m | fresh | train | swept | 587 | 0.451 | 0.457 | -0.006 |
| 15m | flipped | train | none | 268 | 0.566 | 0.469 | 0.097 |
| 15m | flipped | train | present | 59 | 0.390 | 0.469 | -0.079 |
| 15m | flipped | train | cleared | 122 | 0.533 | 0.469 | 0.064 |
| 15m | flipped | train | swept | 87 | 0.517 | 0.469 | 0.048 |
| 15m | fresh | val | none | 312 | 0.484 | 0.449 | 0.035 |
| 15m | fresh | val | present | 538 | 0.401 | 0.449 | -0.047 |
| 15m | fresh | val | cleared | 1078 | 0.435 | 0.449 | -0.013 |
| 15m | fresh | val | swept | 860 | 0.421 | 0.449 | -0.027 |
| 15m | flipped | val | none | 321 | 0.500 | 0.463 | 0.037 |
| 15m | flipped | val | present | 77 | 0.377 | 0.463 | -0.087 |
| 15m | flipped | val | cleared | 141 | 0.536 | 0.463 | 0.072 |
| 15m | flipped | val | swept | 110 | 0.495 | 0.463 | 0.032 |
| 1H | fresh | train | none | 52 | 0.462 | 0.434 | 0.027 |
| 1H | fresh | train | present | 100 | 0.450 | 0.434 | 0.016 |
| 1H | fresh | train | cleared | 163 | 0.460 | 0.434 | 0.026 |
| 1H | fresh | train | swept | 139 | 0.453 | 0.434 | 0.019 |
| 1H | flipped | train | none | 53 | 0.453 | 0.447 | 0.006 |
| 1H | flipped | train | present | 18 | 0.389 | 0.447 | -0.058 |
| 1H | flipped | train | cleared | 24 | 0.750 | 0.447 | 0.303 |
| 1H | flipped | train | swept | 15 | 0.600 | 0.447 | 0.153 |
| 1H | fresh | val | none | 72 | 0.431 | 0.438 | -0.008 |
| 1H | fresh | val | present | 127 | 0.444 | 0.438 | 0.006 |
| 1H | fresh | val | cleared | 228 | 0.395 | 0.438 | -0.043 |
| 1H | fresh | val | swept | 190 | 0.413 | 0.438 | -0.025 |
| 1H | flipped | val | none | 69 | 0.580 | 0.478 | 0.102 |
| 1H | flipped | val | present | 16 | 0.438 | 0.478 | -0.040 |
| 1H | flipped | val | cleared | 36 | 0.417 | 0.478 | -0.061 |
| 1H | flipped | val | swept | 22 | 0.500 | 0.478 | 0.022 |
| 4H | fresh | train | none | 6 | 0.500 | 0.481 | 0.019 |
| 4H | fresh | train | present | 21 | 0.238 | 0.481 | -0.242 |
| 4H | fresh | train | cleared | 50 | 0.480 | 0.481 | -0.001 |
| 4H | fresh | train | swept | 40 | 0.400 | 0.481 | -0.081 |
| 4H | flipped | train | none | 14 | 0.500 | 0.591 | -0.091 |
| 4H | flipped | train | present | 3 | 0.333 | 0.591 | -0.258 |
| 4H | flipped | train | cleared | 5 | 0.600 | 0.591 | 0.009 |
| 4H | flipped | train | swept | 5 | 0.400 | 0.591 | -0.191 |
| 4H | fresh | val | none | 21 | 0.524 | 0.443 | 0.081 |
| 4H | fresh | val | present | 30 | 0.467 | 0.443 | 0.023 |
| 4H | fresh | val | cleared | 67 | 0.507 | 0.443 | 0.064 |
| 4H | fresh | val | swept | 53 | 0.528 | 0.443 | 0.085 |
| 4H | flipped | val | none | 20 | 0.600 | 0.484 | 0.116 |
| 4H | flipped | val | present | 3 | 0.333 | 0.484 | -0.151 |
| 4H | flipped | val | cleared | 8 | 0.500 | 0.484 | 0.016 |
| 4H | flipped | val | swept | 4 | 0.250 | 0.484 | -0.234 |

## Limitations

- One reading of "edge": a symmetric 1 ATR first passage and the 16-candle move. Other distances could differ.
- Random levels match side, distance and period, not the time of day or volatility regime of each real touch.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
