# O1 — GSE v4.0 settings for the 15m Golden Zone

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

400 random configurations plus the defaults (seed 20261011), searched over TradingView inputs only. Objective: expectancy in R after spread and 0.10 slippage, execution RXM-1, on train (2016–2018) with ≥ 150 trades. Every configuration is also scored on validation (2019–2022). The test period is untouched.

Git `d4e2a37d15` · dataset `a637520850ec…`

## Does training performance predict validation?

- Configurations with enough training trades: 157 of 401.
- Positive expectancy on train: 0; on validation: 0; on both: 0.
- Rank correlation of train and validation expectancy (Spearman): -0.113.
- Best validation expectancy of any eligible configuration: -0.055 R.

## GSE defaults

| trial | swing_len | zone_count | flip_on | cluster_on | cluster_atr | eq_atr | break_fallback | require_sweep | space_mult | train_trades | train_expectancy_R | train_profit_factor | train_max_drawdown_R | val_trades | val_expectancy_R | val_profit_factor | val_max_drawdown_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 10 | 8 | True | False | 0.500 | 0.150 | True | False | 2.000 | 309 | -0.378 | 0.493 | 131.3 | 374 | -0.413 | 0.460 | 154.6 |

## Top 20 on train, with their validation results

| trial | swing_len | zone_count | flip_on | cluster_on | cluster_atr | eq_atr | break_fallback | require_sweep | space_mult | train_trades | train_expectancy_R | train_profit_factor | train_max_drawdown_R | val_trades | val_expectancy_R | val_profit_factor | val_max_drawdown_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 206 | 8 | 8 | True | True | 1.000 | 0.100 | False | False | 4.000 | 165 | -0.082 | 0.879 | 42.6 | 210 | -0.338 | 0.584 | 70.9 |
| 300 | 8 | 8 | True | False | 0.500 | 0.100 | False | False | 4.000 | 186 | -0.098 | 0.862 | 51.3 | 230 | -0.437 | 0.463 | 103.0 |
| 66 | 8 | 11 | True | False | 0.500 | 0.300 | False | False | 4.000 | 191 | -0.113 | 0.841 | 54.3 | 219 | -0.388 | 0.518 | 88.3 |
| 99 | 8 | 8 | False | True | 0.500 | 0.050 | False | False | 2.500 | 150 | -0.129 | 0.813 | 37.2 | 207 | -0.395 | 0.488 | 85.6 |
| 128 | 8 | 4 | False | False | 0.500 | 0.100 | False | False | 2.500 | 160 | -0.147 | 0.788 | 41.2 | 217 | -0.407 | 0.476 | 92.3 |
| 298 | 4 | 10 | True | True | 1.000 | 0.100 | True | False | 4.000 | 245 | -0.226 | 0.704 | 73.2 | 340 | -0.489 | 0.414 | 166.3 |
| 200 | 8 | 11 | True | True | 1.000 | 0.200 | False | False | 2.500 | 333 | -0.226 | 0.684 | 89.5 | 424 | -0.340 | 0.562 | 144.3 |
| 70 | 4 | 16 | True | True | 1.500 | 0.100 | False | False | 4.000 | 227 | -0.233 | 0.693 | 71.2 | 298 | -0.567 | 0.325 | 169.1 |
| 136 | 8 | 15 | True | True | 1.500 | 0.150 | True | False | 3.000 | 259 | -0.238 | 0.672 | 74.3 | 351 | -0.460 | 0.435 | 161.3 |
| 52 | 18 | 10 | True | False | 0.500 | 0.300 | True | False | 1.000 | 179 | -0.245 | 0.639 | 47.9 | 196 | -0.055 | 0.911 | 39.9 |
| 289 | 10 | 4 | True | True | 1.500 | 0.300 | False | False | 3.000 | 186 | -0.269 | 0.642 | 66.0 | 220 | -0.277 | 0.630 | 69.6 |
| 366 | 20 | 15 | True | True | 0.800 | 0.100 | True | False | 1.000 | 152 | -0.283 | 0.583 | 50.1 | 182 | -0.175 | 0.735 | 48.4 |
| 370 | 9 | 16 | True | False | 0.500 | 0.050 | False | False | 3.000 | 176 | -0.287 | 0.629 | 63.6 | 283 | -0.459 | 0.431 | 131.5 |
| 384 | 8 | 13 | True | False | 0.500 | 0.150 | False | False | 2.500 | 353 | -0.290 | 0.608 | 112.6 | 443 | -0.395 | 0.503 | 176.6 |
| 260 | 12 | 11 | True | True | 0.300 | 0.200 | False | False | 2.000 | 219 | -0.292 | 0.593 | 71.1 | 286 | -0.361 | 0.513 | 105.1 |
| 230 | 5 | 13 | False | True | 1.500 | 0.150 | False | False | 3.000 | 201 | -0.295 | 0.617 | 84.8 | 253 | -0.374 | 0.513 | 95.9 |
| 301 | 7 | 10 | True | True | 1.500 | 0.100 | True | False | 3.000 | 289 | -0.305 | 0.601 | 97.8 | 388 | -0.353 | 0.554 | 137.4 |
| 193 | 11 | 9 | True | False | 0.500 | 0.200 | False | False | 3.000 | 182 | -0.305 | 0.593 | 70.7 | 202 | -0.409 | 0.468 | 89.5 |
| 97 | 18 | 8 | True | True | 0.800 | 0.100 | True | False | 1.000 | 156 | -0.306 | 0.544 | 48.8 | 184 | -0.133 | 0.798 | 45.1 |
| 257 | 7 | 14 | True | False | 0.500 | 0.300 | True | False | 2.500 | 403 | -0.311 | 0.595 | 136.1 | 545 | -0.323 | 0.577 | 179.4 |

## Selected (best validation expectancy among the top 20 on train)

| TradingView input | Value | Default |
|---|---|---|
| Swing Lookback | 10 | 10 |
| Levels per Side | 4 | 8 |
| Enable Flipped Levels | True | True |
| Merge Nearby Levels | True | False |
| Zone Width (ATR) | 1.5 | 0.5 |
| Equal H/L Tolerance (ATR) | 0.3 | 0.15 |
| Follow Last Structure Break | False | True |
| Require Sweep for Golden Zone | False | False |
| Room to Next Obstacle (ATR) | 3.0 | 2.0 |

Train: 186 trades, expectancy -0.269 R, PF 0.642, max drawdown 66.0 R. Validation: 220 trades, expectancy -0.277 R, PF 0.630, max drawdown 69.6 R.

Its validation figure is optimistic: validation was used to pick it from 20. Only the locked test period can confirm it.

## Sensitivity: one input changed at a time from the selected configuration

A robust choice sits on a plateau: neighbours perform similarly. A spike means luck.

| varied | value | train_trades | train_expectancy_R | val_trades | val_expectancy_R |
|---|---|---|---|---|---|
| swing_len | 4 | 382 | -0.389 | 568 | -0.442 |
| swing_len | 5 | 382 | -0.388 | 502 | -0.448 |
| swing_len | 6 | 313 | -0.379 | 466 | -0.381 |
| swing_len | 7 | 290 | -0.311 | 395 | -0.301 |
| swing_len | 8 | 270 | -0.248 | 339 | -0.311 |
| swing_len | 9 | 223 | -0.298 | 276 | -0.400 |
| swing_len | 11 | 159 | -0.309 | 187 | -0.270 |
| swing_len | 12 | 134 | -0.329 | 176 | -0.312 |
| swing_len | 13 | 116 | -0.355 | 153 | -0.272 |
| swing_len | 14 | 99 | -0.243 | 139 | -0.220 |
| swing_len | 15 | 100 | -0.328 | 125 | -0.263 |
| swing_len | 16 | 85 | -0.382 | 105 | -0.184 |
| swing_len | 17 | 83 | -0.324 | 94 | -0.267 |
| swing_len | 18 | 74 | -0.301 | 77 | -0.231 |
| swing_len | 19 | 70 | -0.441 | 71 | -0.323 |
| swing_len | 20 | 64 | -0.167 | 71 | -0.291 |
| zone_count | 5 | 187 | -0.278 | 212 | -0.324 |
| zone_count | 6 | 178 | -0.282 | 207 | -0.247 |
| zone_count | 7 | 172 | -0.260 | 213 | -0.293 |
| zone_count | 8 | 167 | -0.259 | 219 | -0.239 |
| zone_count | 9 | 170 | -0.253 | 219 | -0.282 |
| zone_count | 10 | 166 | -0.324 | 219 | -0.288 |
| zone_count | 11 | 167 | -0.318 | 224 | -0.305 |
| zone_count | 12 | 169 | -0.310 | 221 | -0.304 |
| zone_count | 13 | 170 | -0.315 | 221 | -0.311 |
| zone_count | 14 | 169 | -0.314 | 224 | -0.345 |
| zone_count | 15 | 168 | -0.359 | 223 | -0.342 |
| zone_count | 16 | 167 | -0.355 | 224 | -0.349 |
| flip_on | False | 56 | -0.336 | 90 | -0.163 |
| cluster_on | False | 204 | -0.256 | 252 | -0.396 |
| cluster_atr | 0.300 | 198 | -0.256 | 249 | -0.382 |
| cluster_atr | 0.500 | 196 | -0.317 | 244 | -0.382 |
| cluster_atr | 0.800 | 194 | -0.249 | 233 | -0.338 |
| cluster_atr | 1.000 | 196 | -0.261 | 225 | -0.291 |
| eq_atr | 0.050 | 140 | -0.378 | 225 | -0.290 |
| eq_atr | 0.100 | 169 | -0.358 | 226 | -0.294 |
| eq_atr | 0.150 | 178 | -0.368 | 235 | -0.291 |
| eq_atr | 0.200 | 186 | -0.269 | 234 | -0.296 |
| break_fallback | True | 197 | -0.290 | 235 | -0.298 |
| require_sweep | True | 1 | -1.055 | 4 | 0.029 |
| space_mult | 1.000 | 329 | -0.283 | 393 | -0.229 |
| space_mult | 1.500 | 297 | -0.312 | 347 | -0.262 |
| space_mult | 2.000 | 258 | -0.319 | 296 | -0.329 |
| space_mult | 2.500 | 221 | -0.296 | 256 | -0.321 |
| space_mult | 4.000 | 142 | -0.188 | 154 | -0.328 |

## Conclusion

**No configuration is positive on validation.** The search does not support recommending any setting: under RXM-1, the Golden Zone has no edge after costs in 2016–2022 at any tested setting.

## Limitations

- 401 configurations were tried, so the best training result is optimistic by construction.
- Only the Golden Zone signal with RXM-1 execution is searched; stops, targets and holding time are not tuned.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).

## Signal or costs? Gross expectancy (mid-price fills, no slippage)

Trial 0 is the GSE defaults. Net = spread + 0.10 slippage, as above.

| trial | train_trades | train_gross_R | train_net_R | val_trades | val_gross_R | val_net_R |
|---|---|---|---|---|---|---|
| 0 | 309.0 | -0.030 | -0.378 | 374.0 | -0.127 | -0.413 |
| 206 | 165.0 | 0.269 | -0.082 | 210.0 | -0.078 | -0.338 |
| 300 | 186.0 | 0.291 | -0.098 | 230.0 | -0.156 | -0.437 |
| 66 | 191.0 | 0.298 | -0.113 | 219.0 | -0.100 | -0.388 |
| 52 | 179.0 | 0.104 | -0.245 | 196.0 | 0.322 | -0.055 |
| 289 | 186.0 | 0.057 | -0.269 | 220.0 | 0.080 | -0.277 |
