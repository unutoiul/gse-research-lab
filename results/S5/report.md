# S5 — GSE's two setups with wider stops and nearer targets

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

Setup A: first touch of a fresh 15m level after a pullback against the 1D + 4H trend. Setup B: first touch of a confirmed 15m flipped level, continuing the trend. The S4 setups and triggers with stops of 2 / 3 / 5 ATR from the entry or 1 ATR beyond the structural invalidation, and targets of 0.25 / 0.5 / 0.75 / 1 R or the nearest opposing structure (at least 0.25 R): 160 variants, all shown. A fixed target of X R needs a win rate above 1 / (1 + X) before costs to break even (0.25 R: 80%, 0.5 R: 67%, 0.75 R: 57%, 1 R: 50%); costs raise it further. Train 2016–2018 picks one per setup; validation 2019–2022 judges it. OANDA bid/ask + 0.10 slippage (net); gross = mid prices, no slippage. Rules: gse_research/setups.py.

Git `75b6259d39` · dataset `66481606d760…`

## Every variant

| setup | trigger | stop | target | train_net_trades | train_net_win_rate | train_net_expectancy_R | train_net_profit_factor | train_net_max_drawdown_R | train_gross_expectancy_R | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_max_drawdown_R | val_gross_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pullback | touch | atr2 | r0.25 | 126 | 0.563 | -0.313 | 0.309 | 40.4 | -0.095 | 144 | 0.618 | -0.240 | 0.390 | 35.9 | -0.107 |
| A_pullback | touch | atr2 | r0.5 | 123 | 0.447 | -0.351 | 0.388 | 44.7 | -0.101 | 143 | 0.531 | -0.219 | 0.548 | 32.4 | -0.095 |
| A_pullback | touch | atr2 | r0.75 | 123 | 0.398 | -0.326 | 0.477 | 43.3 | -0.113 | 142 | 0.479 | -0.179 | 0.667 | 30.3 | -0.065 |
| A_pullback | touch | atr2 | r1 | 123 | 0.350 | -0.326 | 0.517 | 45.0 | -0.096 | 140 | 0.421 | -0.175 | 0.706 | 28.1 | -0.070 |
| A_pullback | touch | atr2 | near | 114 | 0.298 | -0.178 | 0.758 | 32.6 | 0.091 | 124 | 0.258 | -0.142 | 0.814 | 31.2 | -0.099 |
| A_pullback | touch | atr3 | r0.25 | 121 | 0.636 | -0.211 | 0.430 | 26.2 | -0.061 | 141 | 0.660 | -0.184 | 0.473 | 27.6 | -0.070 |
| A_pullback | touch | atr3 | r0.5 | 118 | 0.551 | -0.183 | 0.600 | 23.1 | -0.029 | 138 | 0.580 | -0.140 | 0.674 | 23.1 | -0.079 |
| A_pullback | touch | atr3 | r0.75 | 116 | 0.491 | -0.153 | 0.706 | 22.5 | -0.016 | 135 | 0.519 | -0.103 | 0.790 | 18.2 | -0.084 |
| A_pullback | touch | atr3 | r1 | 114 | 0.456 | -0.101 | 0.818 | 17.2 | 0.037 | 125 | 0.416 | -0.180 | 0.698 | 24.5 | -0.128 |
| A_pullback | touch | atr3 | near | 107 | 0.430 | -0.059 | 0.900 | 14.8 | -0.007 | 117 | 0.350 | -0.135 | 0.797 | 23.4 | -0.119 |
| A_pullback | touch | atr5 | r0.25 | 114 | 0.772 | -0.033 | 0.852 | 8.798 | 0.038 | 125 | 0.728 | -0.094 | 0.660 | 15.2 | -0.037 |
| A_pullback | touch | atr5 | r0.5 | 106 | 0.660 | -0.009 | 0.973 | 10.4 | 0.050 | 112 | 0.643 | -0.040 | 0.888 | 9.948 | -0.052 |
| A_pullback | touch | atr5 | r0.75 | 99 | 0.616 | 0.078 | 1.205 | 10.2 | 0.117 | 103 | 0.524 | -0.089 | 0.816 | 12.5 | -0.042 |
| A_pullback | touch | atr5 | r1 | 91 | 0.560 | 0.117 | 1.262 | 9.212 | 0.190 | 93 | 0.473 | -0.061 | 0.887 | 13.4 | -0.019 |
| A_pullback | touch | atr5 | near | 93 | 0.559 | -0.010 | 0.978 | 12.8 | 0.053 | 99 | 0.485 | -0.062 | 0.881 | 10.0 | -0.057 |
| A_pullback | touch | structural_buf1 | r0.25 | 129 | 0.442 | -0.489 | 0.183 | 64.0 | -0.212 | 150 | 0.487 | -0.422 | 0.223 | 63.3 | -0.271 |
| A_pullback | touch | structural_buf1 | r0.5 | 128 | 0.383 | -0.471 | 0.287 | 62.3 | -0.142 | 149 | 0.409 | -0.419 | 0.328 | 63.4 | -0.224 |
| A_pullback | touch | structural_buf1 | r0.75 | 127 | 0.346 | -0.442 | 0.369 | 56.5 | -0.161 | 148 | 0.372 | -0.386 | 0.419 | 57.6 | -0.167 |
| A_pullback | touch | structural_buf1 | r1 | 126 | 0.262 | -0.529 | 0.330 | 67.5 | -0.168 | 148 | 0.338 | -0.362 | 0.483 | 56.1 | -0.131 |
| A_pullback | touch | structural_buf1 | near | 120 | 0.192 | -0.295 | 0.665 | 40.1 | -0.016 | 131 | 0.160 | -0.298 | 0.664 | 44.6 | -0.108 |
| A_pullback | rejection | atr2 | r0.25 | 10 | 0.900 | 0.053 | 1.500 | 1.066 | 0.156 | 12 | 0.750 | -0.139 | 0.506 | 2.385 | -0.059 |
| A_pullback | rejection | atr2 | r0.5 | 10 | 0.700 | -0.029 | 0.913 | 1.793 | 0.081 | 12 | 0.417 | -0.460 | 0.283 | 5.524 | -0.371 |
| A_pullback | rejection | atr2 | r0.75 | 10 | 0.400 | -0.390 | 0.412 | 3.897 | -0.269 | 12 | 0.333 | -0.504 | 0.310 | 6.267 | -0.413 |
| A_pullback | rejection | atr2 | r1 | 10 | 0.200 | -0.699 | 0.212 | 6.995 | -0.568 | 12 | 0.250 | -0.589 | 0.285 | 7.066 | -0.329 |
| A_pullback | rejection | atr2 | near | 10 | 0.100 | -0.927 | 0.073 | 9.273 | -0.791 | 12 | 0.250 | -0.624 | 0.237 | 7.504 | -0.532 |
| A_pullback | rejection | atr3 | r0.25 | 10 | 0.700 | -0.177 | 0.449 | 1.975 | 0.021 | 12 | 0.667 | -0.219 | 0.387 | 3.209 | -0.060 |
| A_pullback | rejection | atr3 | r0.5 | 10 | 0.500 | -0.308 | 0.427 | 3.081 | -0.229 | 12 | 0.417 | -0.431 | 0.305 | 5.169 | -0.372 |
| A_pullback | rejection | atr3 | r0.75 | 10 | 0.300 | -0.540 | 0.284 | 5.398 | -0.454 | 12 | 0.333 | -0.474 | 0.333 | 5.687 | -0.361 |
| A_pullback | rejection | atr3 | r1 | 10 | 0.300 | -0.465 | 0.384 | 4.646 | -0.379 | 12 | 0.250 | -0.558 | 0.301 | 6.699 | -0.270 |
| A_pullback | rejection | atr3 | near | 10 | 0.200 | -0.759 | 0.119 | 7.594 | -0.670 | 12 | 0.250 | -0.666 | 0.163 | 7.994 | -0.341 |
| A_pullback | rejection | atr5 | r0.25 | 10 | 0.700 | -0.157 | 0.499 | 2.232 | 0.137 | 12 | 0.667 | -0.198 | 0.430 | 3.025 | -0.165 |
| A_pullback | rejection | atr5 | r0.5 | 10 | 0.600 | -0.134 | 0.679 | 2.752 | -0.088 | 11 | 0.545 | -0.214 | 0.548 | 2.687 | -0.180 |
| A_pullback | rejection | atr5 | r0.75 | 10 | 0.500 | -0.161 | 0.692 | 3.772 | -0.112 | 11 | 0.364 | -0.397 | 0.398 | 4.371 | -0.362 |
| A_pullback | rejection | atr5 | r1 | 10 | 0.500 | -0.036 | 0.931 | 3.272 | 0.013 | 9 | 0.222 | -0.591 | 0.267 | 5.321 | -0.555 |
| A_pullback | rejection | atr5 | near | 10 | 0.500 | -0.166 | 0.684 | 4.620 | -0.113 | 9 | 0.222 | -0.647 | 0.198 | 5.827 | -0.612 |
| A_pullback | rejection | structural_buf1 | r0.25 | 10 | 0.900 | 0.053 | 1.495 | 1.076 | 0.154 | 12 | 0.667 | -0.228 | 0.366 | 3.272 | -0.164 |
| A_pullback | rejection | structural_buf1 | r0.5 | 10 | 0.600 | -0.180 | 0.589 | 2.467 | -0.070 | 12 | 0.500 | -0.315 | 0.416 | 3.774 | -0.247 |
| A_pullback | rejection | structural_buf1 | r0.75 | 10 | 0.400 | -0.389 | 0.414 | 3.892 | -0.270 | 12 | 0.417 | -0.337 | 0.462 | 4.309 | -0.268 |
| A_pullback | rejection | structural_buf1 | r1 | 10 | 0.200 | -0.699 | 0.214 | 6.994 | -0.369 | 12 | 0.250 | -0.569 | 0.297 | 6.830 | -0.163 |
| A_pullback | rejection | structural_buf1 | near | 10 | 0.100 | -0.942 | 0.057 | 9.424 | -0.808 | 12 | 0.250 | -0.669 | 0.167 | 8.033 | -0.596 |
| A_pullback | sweep_reclaim | atr2 | r0.25 | 80 | 0.738 | -0.179 | 0.397 | 15.2 | -0.024 | 92 | 0.717 | -0.199 | 0.381 | 19.1 | -0.033 |
| A_pullback | sweep_reclaim | atr2 | r0.5 | 80 | 0.625 | -0.167 | 0.606 | 15.6 | -0.055 | 88 | 0.534 | -0.299 | 0.431 | 27.5 | -0.145 |
| A_pullback | sweep_reclaim | atr2 | r0.75 | 80 | 0.525 | -0.189 | 0.648 | 17.4 | -0.030 | 88 | 0.432 | -0.347 | 0.456 | 31.9 | -0.193 |
| A_pullback | sweep_reclaim | atr2 | r1 | 79 | 0.418 | -0.278 | 0.581 | 25.4 | -0.117 | 87 | 0.368 | -0.368 | 0.481 | 33.9 | -0.183 |
| A_pullback | sweep_reclaim | atr2 | near | 77 | 0.390 | -0.223 | 0.677 | 23.4 | -0.102 | 79 | 0.291 | -0.333 | 0.579 | 33.0 | -0.208 |
| A_pullback | sweep_reclaim | atr3 | r0.25 | 80 | 0.700 | -0.193 | 0.406 | 16.5 | -0.014 | 88 | 0.670 | -0.226 | 0.370 | 20.5 | -0.061 |
| A_pullback | sweep_reclaim | atr3 | r0.5 | 80 | 0.575 | -0.209 | 0.548 | 18.1 | -0.027 | 86 | 0.535 | -0.265 | 0.475 | 23.7 | -0.161 |
| A_pullback | sweep_reclaim | atr3 | r0.75 | 79 | 0.456 | -0.277 | 0.533 | 24.9 | -0.097 | 82 | 0.451 | -0.278 | 0.533 | 24.2 | -0.177 |
| A_pullback | sweep_reclaim | atr3 | r1 | 79 | 0.418 | -0.240 | 0.622 | 23.5 | -0.020 | 78 | 0.410 | -0.245 | 0.615 | 21.0 | -0.127 |
| A_pullback | sweep_reclaim | atr3 | near | 76 | 0.434 | -0.233 | 0.621 | 21.9 | -0.048 | 75 | 0.387 | -0.236 | 0.644 | 23.3 | -0.103 |
| A_pullback | sweep_reclaim | atr5 | r0.25 | 77 | 0.792 | -0.050 | 0.773 | 5.357 | 0.058 | 81 | 0.716 | -0.144 | 0.520 | 12.5 | -0.065 |
| A_pullback | sweep_reclaim | atr5 | r0.5 | 75 | 0.640 | -0.082 | 0.783 | 10.2 | -0.044 | 70 | 0.571 | -0.182 | 0.596 | 14.1 | -0.091 |
| A_pullback | sweep_reclaim | atr5 | r0.75 | 72 | 0.597 | 0.003 | 1.007 | 5.913 | 0.073 | 66 | 0.485 | -0.191 | 0.646 | 14.8 | -0.084 |
| A_pullback | sweep_reclaim | atr5 | r1 | 67 | 0.522 | -0.001 | 0.998 | 7.846 | 0.095 | 66 | 0.409 | -0.222 | 0.641 | 17.6 | -0.111 |
| A_pullback | sweep_reclaim | atr5 | near | 67 | 0.597 | -0.085 | 0.800 | 11.2 | -0.028 | 63 | 0.476 | -0.158 | 0.713 | 14.2 | -0.028 |
| A_pullback | sweep_reclaim | structural_buf1 | r0.25 | 80 | 0.688 | -0.222 | 0.324 | 18.7 | 0.011 | 92 | 0.652 | -0.251 | 0.303 | 23.9 | -0.046 |
| A_pullback | sweep_reclaim | structural_buf1 | r0.5 | 80 | 0.588 | -0.236 | 0.498 | 21.1 | -0.036 | 89 | 0.517 | -0.338 | 0.389 | 31.2 | -0.105 |
| A_pullback | sweep_reclaim | structural_buf1 | r0.75 | 80 | 0.512 | -0.224 | 0.598 | 20.1 | -0.029 | 88 | 0.420 | -0.380 | 0.424 | 35.3 | -0.182 |
| A_pullback | sweep_reclaim | structural_buf1 | r1 | 80 | 0.450 | -0.224 | 0.645 | 21.4 | 0.059 | 86 | 0.349 | -0.417 | 0.434 | 37.7 | -0.262 |
| A_pullback | sweep_reclaim | structural_buf1 | near | 77 | 0.364 | -0.245 | 0.667 | 26.2 | -0.002 | 80 | 0.262 | -0.402 | 0.519 | 37.9 | -0.283 |
| A_pullback | bos | atr2 | r0.25 | 29 | 0.724 | -0.187 | 0.364 | 6.265 | -0.072 | 33 | 0.697 | -0.223 | 0.338 | 8.253 | -0.085 |
| A_pullback | bos | atr2 | r0.5 | 29 | 0.586 | -0.219 | 0.513 | 7.627 | -0.098 | 33 | 0.576 | -0.234 | 0.504 | 9.829 | -0.039 |
| A_pullback | bos | atr2 | r0.75 | 29 | 0.517 | -0.196 | 0.632 | 8.031 | -0.012 | 32 | 0.469 | -0.279 | 0.535 | 11.7 | -0.070 |
| A_pullback | bos | atr2 | r1 | 29 | 0.448 | -0.208 | 0.663 | 8.813 | -0.011 | 32 | 0.375 | -0.352 | 0.499 | 15.6 | -0.124 |
| A_pullback | bos | atr2 | near | 28 | 0.464 | -0.199 | 0.665 | 8.828 | -0.072 | 30 | 0.300 | -0.490 | 0.367 | 18.2 | -0.393 |
| A_pullback | bos | atr3 | r0.25 | 29 | 0.724 | -0.157 | 0.471 | 5.161 | -0.037 | 33 | 0.697 | -0.190 | 0.414 | 7.463 | -0.049 |
| A_pullback | bos | atr3 | r0.5 | 29 | 0.552 | -0.292 | 0.459 | 9.822 | -0.149 | 32 | 0.469 | -0.363 | 0.371 | 12.8 | -0.128 |
| A_pullback | bos | atr3 | r0.75 | 29 | 0.517 | -0.215 | 0.627 | 8.888 | -0.124 | 32 | 0.375 | -0.412 | 0.392 | 16.0 | -0.322 |
| A_pullback | bos | atr3 | r1 | 29 | 0.483 | -0.156 | 0.748 | 7.384 | -0.063 | 32 | 0.281 | -0.507 | 0.346 | 18.8 | -0.419 |
| A_pullback | bos | atr3 | near | 28 | 0.464 | -0.358 | 0.439 | 11.6 | -0.264 | 30 | 0.300 | -0.526 | 0.299 | 19.4 | -0.442 |
| A_pullback | bos | atr5 | r0.25 | 29 | 0.793 | -0.045 | 0.792 | 2.902 | 0.000 | 31 | 0.677 | -0.190 | 0.437 | 6.407 | -0.101 |
| A_pullback | bos | atr5 | r0.5 | 29 | 0.655 | -0.074 | 0.807 | 4.670 | 0.031 | 31 | 0.484 | -0.314 | 0.420 | 11.1 | -0.200 |
| A_pullback | bos | atr5 | r0.75 | 28 | 0.571 | -0.057 | 0.878 | 5.946 | 0.022 | 31 | 0.387 | -0.363 | 0.434 | 12.5 | -0.241 |
| A_pullback | bos | atr5 | r1 | 27 | 0.519 | -0.042 | 0.920 | 6.079 | 0.015 | 31 | 0.355 | -0.331 | 0.509 | 11.2 | -0.199 |
| A_pullback | bos | atr5 | near | 26 | 0.577 | -0.062 | 0.867 | 5.894 | -0.007 | 29 | 0.379 | -0.425 | 0.345 | 14.1 | -0.312 |
| A_pullback | bos | structural_buf1 | r0.25 | 29 | 0.724 | -0.153 | 0.485 | 5.458 | -0.038 | 33 | 0.727 | -0.146 | 0.496 | 6.306 | -0.086 |
| A_pullback | bos | structural_buf1 | r0.5 | 29 | 0.586 | -0.200 | 0.569 | 7.179 | -0.120 | 32 | 0.438 | -0.403 | 0.333 | 14.1 | -0.224 |
| A_pullback | bos | structural_buf1 | r0.75 | 29 | 0.448 | -0.299 | 0.516 | 10.8 | -0.154 | 32 | 0.375 | -0.405 | 0.397 | 15.8 | -0.321 |
| A_pullback | bos | structural_buf1 | r1 | 29 | 0.414 | -0.273 | 0.582 | 10.3 | -0.187 | 32 | 0.344 | -0.374 | 0.469 | 16.6 | -0.289 |
| A_pullback | bos | structural_buf1 | near | 27 | 0.407 | -0.328 | 0.506 | 12.1 | -0.240 | 30 | 0.300 | -0.547 | 0.265 | 19.1 | -0.471 |
| B_flip | touch | atr2 | r0.25 | 50 | 0.740 | -0.082 | 0.691 | 5.354 | -0.020 | 50 | 0.700 | -0.136 | 0.562 | 9.042 | -0.036 |
| B_flip | touch | atr2 | r0.5 | 50 | 0.660 | -0.020 | 0.942 | 5.968 | 0.066 | 49 | 0.592 | -0.126 | 0.701 | 8.132 | 0.045 |
| B_flip | touch | atr2 | r0.75 | 50 | 0.600 | 0.038 | 1.092 | 6.345 | 0.062 | 49 | 0.531 | -0.088 | 0.818 | 9.481 | 0.093 |
| B_flip | touch | atr2 | r1 | 49 | 0.490 | -0.036 | 0.932 | 7.480 | 0.144 | 49 | 0.449 | -0.121 | 0.788 | 9.884 | 0.071 |
| B_flip | touch | atr2 | near | 49 | 0.469 | -0.172 | 0.685 | 12.0 | -0.057 | 42 | 0.333 | -0.355 | 0.483 | 17.3 | -0.177 |
| B_flip | touch | atr3 | r0.25 | 50 | 0.720 | -0.105 | 0.630 | 6.257 | 0.039 | 49 | 0.694 | -0.140 | 0.553 | 7.819 | -0.018 |
| B_flip | touch | atr3 | r0.5 | 50 | 0.620 | -0.078 | 0.799 | 6.869 | 0.057 | 49 | 0.592 | -0.122 | 0.708 | 8.403 | -0.009 |
| B_flip | touch | atr3 | r0.75 | 49 | 0.429 | -0.262 | 0.551 | 15.6 | -0.027 | 49 | 0.510 | -0.118 | 0.764 | 9.706 | -0.001 |
| B_flip | touch | atr3 | r1 | 48 | 0.375 | -0.264 | 0.587 | 17.6 | 0.023 | 46 | 0.391 | -0.230 | 0.630 | 12.6 | -0.000 |
| B_flip | touch | atr3 | near | 49 | 0.449 | -0.293 | 0.478 | 16.2 | -0.031 | 42 | 0.333 | -0.438 | 0.356 | 18.4 | -0.242 |
| B_flip | touch | atr5 | r0.25 | 50 | 0.760 | -0.053 | 0.783 | 5.338 | 0.011 | 49 | 0.755 | -0.060 | 0.758 | 4.925 | 0.026 |
| B_flip | touch | atr5 | r0.5 | 49 | 0.551 | -0.179 | 0.606 | 10.3 | -0.070 | 47 | 0.723 | 0.081 | 1.288 | 2.596 | 0.111 |
| B_flip | touch | atr5 | r0.75 | 45 | 0.467 | -0.190 | 0.648 | 12.3 | -0.156 | 39 | 0.564 | -0.018 | 0.958 | 6.567 | 0.089 |
| B_flip | touch | atr5 | r1 | 41 | 0.390 | -0.245 | 0.614 | 16.0 | -0.176 | 39 | 0.487 | -0.032 | 0.939 | 6.066 | 0.067 |
| B_flip | touch | atr5 | near | 41 | 0.488 | -0.160 | 0.693 | 11.3 | -0.114 | 40 | 0.525 | -0.103 | 0.786 | 6.051 | -0.097 |
| B_flip | touch | structural_buf1 | r0.25 | 50 | 0.660 | -0.190 | 0.463 | 9.985 | -0.077 | 50 | 0.560 | -0.322 | 0.301 | 18.4 | -0.161 |
| B_flip | touch | structural_buf1 | r0.5 | 50 | 0.600 | -0.119 | 0.716 | 6.925 | 0.053 | 49 | 0.510 | -0.259 | 0.496 | 15.1 | -0.117 |
| B_flip | touch | structural_buf1 | r0.75 | 50 | 0.540 | -0.077 | 0.839 | 5.795 | 0.138 | 49 | 0.469 | -0.204 | 0.632 | 13.5 | -0.032 |
| B_flip | touch | structural_buf1 | r1 | 50 | 0.480 | -0.065 | 0.880 | 6.192 | 0.116 | 49 | 0.429 | -0.171 | 0.715 | 13.3 | 0.035 |
| B_flip | touch | structural_buf1 | near | 49 | 0.367 | -0.301 | 0.546 | 15.4 | -0.271 | 46 | 0.283 | -0.424 | 0.434 | 21.4 | -0.192 |
| B_flip | rejection | atr2 | r0.25 | 3 | 0.667 | -0.247 | 0.338 | 1.121 | -0.175 | 4 | 1.000 | 0.193 | ∞ | 0.000 | 0.255 |
| B_flip | rejection | atr2 | r0.5 | 3 | 0.333 | -0.590 | 0.194 | 2.196 | -0.508 | 4 | 1.000 | 0.443 | ∞ | 0.000 | 0.505 |
| B_flip | rejection | atr2 | r0.75 | 3 | 0.333 | -0.506 | 0.308 | 2.196 | -0.424 | 4 | 0.750 | 0.251 | 1.944 | 1.065 | 0.317 |
| B_flip | rejection | atr2 | r1 | 3 | 0.333 | -0.423 | 0.422 | 2.196 | -0.341 | 4 | 0.500 | -0.065 | 0.877 | 2.120 | 0.006 |
| B_flip | rejection | atr2 | near | 3 | 0.667 | 0.072 | 1.194 | 1.121 | 0.145 | 4 | 0.500 | -0.281 | 0.470 | 2.120 | -0.210 |
| B_flip | rejection | atr3 | r0.25 | 3 | 0.667 | -0.220 | 0.389 | 1.081 | -0.172 | 4 | 1.000 | 0.212 | ∞ | 0.000 | 0.254 |
| B_flip | rejection | atr3 | r0.5 | 3 | 0.333 | -0.560 | 0.212 | 2.131 | -0.505 | 4 | 1.000 | 0.462 | ∞ | 0.000 | 0.504 |
| B_flip | rejection | atr3 | r0.75 | 3 | 0.333 | -0.477 | 0.329 | 2.131 | -0.422 | 4 | 0.750 | 0.272 | 2.048 | 1.037 | 0.316 |
| B_flip | rejection | atr3 | r1 | 3 | 0.333 | -0.393 | 0.447 | 2.131 | -0.338 | 4 | 0.500 | -0.044 | 0.915 | 1.136 | 0.504 |
| B_flip | rejection | atr3 | near | 3 | 0.333 | -0.465 | 0.345 | 2.131 | -0.410 | 4 | 0.750 | 0.070 | 1.268 | 1.037 | 0.114 |
| B_flip | rejection | atr5 | r0.25 | 3 | 0.667 | -0.199 | 0.420 | 1.030 | -0.170 | 4 | 1.000 | 0.227 | ∞ | 0.000 | 0.252 |
| B_flip | rejection | atr5 | r0.5 | 3 | 0.667 | -0.033 | 0.905 | 1.030 | -0.003 | 4 | 0.750 | 0.100 | 1.393 | 1.022 | 0.127 |
| B_flip | rejection | atr5 | r0.75 | 3 | 0.667 | 0.134 | 1.391 | 1.030 | 0.164 | 4 | 0.750 | 0.288 | 2.126 | 1.022 | 0.314 |
| B_flip | rejection | atr5 | r1 | 3 | 0.333 | -0.369 | 0.467 | 2.079 | 0.330 | 4 | 0.750 | 0.476 | 2.861 | 1.022 | 0.502 |
| B_flip | rejection | atr5 | near | 3 | 0.333 | -0.546 | 0.212 | 2.079 | -0.513 | 4 | 0.750 | -0.019 | 0.924 | 1.022 | 0.007 |
| B_flip | rejection | structural_buf1 | r0.25 | 3 | 0.667 | -0.245 | 0.346 | 1.124 | -0.172 | 4 | 1.000 | 0.204 | ∞ | 0.000 | 0.255 |
| B_flip | rejection | structural_buf1 | r0.5 | 3 | 0.333 | -0.590 | 0.199 | 2.212 | -0.006 | 4 | 1.000 | 0.454 | ∞ | 0.000 | 0.505 |
| B_flip | rejection | structural_buf1 | r0.75 | 3 | 0.333 | -0.507 | 0.313 | 2.212 | -0.422 | 4 | 0.750 | 0.264 | 2.009 | 1.045 | 0.318 |
| B_flip | rejection | structural_buf1 | r1 | 3 | 0.333 | -0.423 | 0.426 | 2.212 | -0.338 | 4 | 0.500 | -0.054 | 0.899 | 1.160 | 0.505 |
| B_flip | rejection | structural_buf1 | near | 3 | 0.667 | 0.009 | 1.024 | 1.124 | 0.083 | 4 | 0.750 | 0.099 | 1.381 | 1.045 | 0.153 |
| B_flip | sweep_reclaim | atr2 | r0.25 | 30 | 0.867 | -0.005 | 0.964 | 1.524 | 0.125 | 27 | 0.852 | -0.018 | 0.900 | 2.391 | 0.115 |
| B_flip | sweep_reclaim | atr2 | r0.5 | 30 | 0.700 | -0.044 | 0.871 | 3.719 | 0.150 | 25 | 0.840 | 0.175 | 1.915 | 2.144 | 0.273 |
| B_flip | sweep_reclaim | atr2 | r0.75 | 30 | 0.600 | -0.047 | 0.894 | 3.953 | 0.167 | 25 | 0.760 | 0.242 | 1.863 | 3.700 | 0.334 |
| B_flip | sweep_reclaim | atr2 | r1 | 30 | 0.533 | -0.033 | 0.936 | 5.152 | 0.201 | 25 | 0.720 | 0.351 | 2.093 | 3.700 | 0.444 |
| B_flip | sweep_reclaim | atr2 | near | 29 | 0.414 | -0.357 | 0.458 | 10.3 | -0.200 | 25 | 0.480 | -0.024 | 0.958 | 9.723 | 0.074 |
| B_flip | sweep_reclaim | atr3 | r0.25 | 30 | 0.833 | -0.018 | 0.900 | 2.541 | 0.083 | 26 | 0.846 | 0.002 | 1.013 | 2.178 | 0.109 |
| B_flip | sweep_reclaim | atr3 | r0.5 | 30 | 0.667 | -0.063 | 0.823 | 3.226 | 0.100 | 25 | 0.800 | 0.141 | 1.629 | 3.468 | 0.203 |
| B_flip | sweep_reclaim | atr3 | r0.75 | 30 | 0.600 | -0.015 | 0.964 | 5.520 | 0.167 | 24 | 0.750 | 0.253 | 1.912 | 3.468 | 0.316 |
| B_flip | sweep_reclaim | atr3 | r1 | 29 | 0.483 | -0.103 | 0.816 | 6.788 | 0.035 | 23 | 0.391 | -0.283 | 0.569 | 8.409 | 0.087 |
| B_flip | sweep_reclaim | atr3 | near | 28 | 0.464 | -0.288 | 0.502 | 8.071 | -0.003 | 24 | 0.458 | -0.206 | 0.649 | 9.107 | -0.052 |
| B_flip | sweep_reclaim | atr5 | r0.25 | 30 | 0.833 | 0.006 | 1.033 | 1.791 | 0.077 | 25 | 0.880 | 0.066 | 1.508 | 2.008 | 0.102 |
| B_flip | sweep_reclaim | atr5 | r0.5 | 29 | 0.621 | -0.108 | 0.728 | 5.937 | -0.007 | 23 | 0.739 | 0.074 | 1.271 | 2.613 | 0.111 |
| B_flip | sweep_reclaim | atr5 | r0.75 | 28 | 0.500 | -0.165 | 0.685 | 8.906 | -0.132 | 22 | 0.636 | 0.078 | 1.205 | 3.393 | 0.116 |
| B_flip | sweep_reclaim | atr5 | r1 | 27 | 0.444 | -0.151 | 0.740 | 7.870 | -0.078 | 22 | 0.455 | -0.128 | 0.775 | 4.409 | 0.002 |
| B_flip | sweep_reclaim | atr5 | near | 25 | 0.560 | -0.149 | 0.675 | 5.590 | -0.120 | 23 | 0.609 | 0.207 | 1.504 | 3.299 | 0.245 |
| B_flip | sweep_reclaim | structural_buf1 | r0.25 | 30 | 0.833 | -0.064 | 0.666 | 2.548 | 0.133 | 27 | 0.852 | -0.027 | 0.849 | 2.411 | 0.069 |
| B_flip | sweep_reclaim | structural_buf1 | r0.5 | 30 | 0.667 | -0.111 | 0.709 | 5.593 | 0.152 | 26 | 0.846 | 0.176 | 1.966 | 2.160 | 0.274 |
| B_flip | sweep_reclaim | structural_buf1 | r0.75 | 30 | 0.600 | -0.064 | 0.859 | 4.143 | 0.110 | 25 | 0.800 | 0.302 | 2.275 | 3.722 | 0.475 |
| B_flip | sweep_reclaim | structural_buf1 | r1 | 30 | 0.533 | -0.050 | 0.905 | 5.180 | 0.203 | 25 | 0.640 | 0.178 | 1.426 | 5.139 | 0.525 |
| B_flip | sweep_reclaim | structural_buf1 | near | 28 | 0.393 | -0.396 | 0.434 | 11.1 | -0.271 | 25 | 0.520 | 0.167 | 1.304 | 7.219 | 0.277 |
| B_flip | bos | atr2 | r0.25 | 12 | 0.583 | -0.364 | 0.204 | 5.223 | -0.055 | 11 | 0.545 | -0.447 | 0.169 | 5.621 | -0.203 |
| B_flip | bos | atr2 | r0.5 | 12 | 0.583 | -0.219 | 0.522 | 4.724 | 0.008 | 11 | 0.455 | -0.448 | 0.292 | 5.777 | -0.317 |
| B_flip | bos | atr2 | r0.75 | 12 | 0.583 | -0.073 | 0.841 | 4.449 | 0.119 | 11 | 0.273 | -0.656 | 0.213 | 7.879 | -0.521 |
| B_flip | bos | atr2 | r1 | 12 | 0.500 | -0.097 | 0.824 | 4.813 | 0.278 | 11 | 0.273 | -0.587 | 0.295 | 7.377 | -0.453 |
| B_flip | bos | atr2 | near | 12 | 0.333 | -0.554 | 0.246 | 6.649 | -0.317 | 11 | 0.273 | -0.791 | 0.056 | 9.073 | -0.655 |
| B_flip | bos | atr3 | r0.25 | 12 | 0.750 | -0.122 | 0.546 | 3.032 | -0.057 | 11 | 0.545 | -0.404 | 0.208 | 5.246 | -0.317 |
| B_flip | bos | atr3 | r0.5 | 11 | 0.636 | -0.110 | 0.719 | 4.299 | -0.042 | 11 | 0.273 | -0.680 | 0.148 | 7.919 | -0.590 |
| B_flip | bos | atr3 | r0.75 | 11 | 0.545 | -0.112 | 0.770 | 4.299 | -0.042 | 11 | 0.273 | -0.611 | 0.234 | 7.420 | -0.522 |
| B_flip | bos | atr3 | r1 | 10 | 0.300 | -0.464 | 0.382 | 5.486 | -0.392 | 11 | 0.273 | -0.543 | 0.319 | 6.918 | -0.452 |
| B_flip | bos | atr3 | near | 12 | 0.417 | -0.466 | 0.256 | 5.591 | -0.394 | 11 | 0.273 | -0.599 | 0.250 | 6.985 | -0.509 |
| B_flip | bos | atr5 | r0.25 | 12 | 0.750 | -0.098 | 0.626 | 2.910 | -0.059 | 11 | 0.545 | -0.368 | 0.241 | 4.270 | -0.318 |
| B_flip | bos | atr5 | r0.5 | 11 | 0.545 | -0.221 | 0.536 | 3.725 | -0.042 | 11 | 0.545 | -0.232 | 0.522 | 3.020 | -0.181 |
| B_flip | bos | atr5 | r0.75 | 10 | 0.400 | -0.337 | 0.465 | 3.476 | -0.295 | 11 | 0.545 | -0.096 | 0.803 | 2.264 | -0.045 |
| B_flip | bos | atr5 | r1 | 10 | 0.400 | -0.237 | 0.624 | 3.225 | -0.195 | 11 | 0.455 | -0.142 | 0.755 | 2.527 | -0.090 |
| B_flip | bos | atr5 | near | 11 | 0.545 | -0.176 | 0.629 | 3.849 | -0.135 | 10 | 0.400 | -0.475 | 0.256 | 4.995 | -0.422 |
| B_flip | bos | structural_buf1 | r0.25 | 12 | 0.667 | -0.228 | 0.362 | 4.289 | -0.160 | 11 | 0.545 | -0.394 | 0.214 | 5.141 | -0.318 |
| B_flip | bos | structural_buf1 | r0.5 | 11 | 0.636 | -0.110 | 0.718 | 4.289 | -0.040 | 11 | 0.273 | -0.670 | 0.150 | 7.812 | -0.454 |
| B_flip | bos | structural_buf1 | r0.75 | 10 | 0.400 | -0.363 | 0.434 | 5.383 | -0.040 | 11 | 0.273 | -0.602 | 0.237 | 7.313 | -0.363 |
| B_flip | bos | structural_buf1 | r1 | 10 | 0.300 | -0.466 | 0.378 | 5.481 | -0.391 | 11 | 0.273 | -0.533 | 0.324 | 6.810 | -0.272 |
| B_flip | bos | structural_buf1 | near | 12 | 0.417 | -0.479 | 0.234 | 5.742 | -0.405 | 11 | 0.273 | -0.583 | 0.261 | 6.829 | -0.378 |

## Selected on train, judged on validation

| setup | trigger | stop | target | train_net_trades | train_net_expectancy_R | train_net_sqn | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_ci_low | val_gross_expectancy_R | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pullback | touch | atr5 | r1 | 91 | 0.117 | 1.107 | 93 | 0.473 | -0.061 | 0.887 | -0.254 | -0.019 | rejected |
| B_flip | touch | atr2 | r0.75 | 50 | 0.038 | 0.304 | 49 | 0.531 | -0.088 | 0.818 | -0.355 | 0.093 | inconclusive |

## Monte Carlo

Random entries: 50 runs with the same number of entries at random 15m closes in the trend's direction, with stop and target sizes drawn from the real trades. share_random_at_least_real is the share of random runs that did as well as the setup (small = the entries carry information). Trade resampling: one year of the real trades redrawn 5,000 times (yearly R, losing-year chance, drawdowns in R).

| setup | period | real_avg_R | random_avg_R_mean | random_p5 | random_p95 | share_random_at_least_real | trades_per_year | year_R_median | year_R_p5 | year_R_p95 | losing_year_chance | max_drawdown_R_median | max_drawdown_R_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pullback | train | 0.117 | 0.004 | -0.161 | 0.185 | 0.120 | 30 | 3.776 | -6.270 | 12.2 | 0.284 | 4.116 | 9.225 |
| A_pullback | val | -0.061 | -0.059 | -0.224 | 0.091 | 0.520 | 23 | -1.161 | -9.209 | 6.881 | 0.609 | 5.136 | 11.2 |
| B_flip | train | 0.038 | -0.196 | -0.395 | 0.018 | 0.020 | 17 | 0.353 | -5.112 | 7.350 | 0.354 | 3.124 | 6.936 |
| B_flip | val | -0.088 | -0.183 | -0.409 | -0.010 | 0.340 | 12 | -1.659 | -5.347 | 3.656 | 0.528 | 3.358 | 7.008 |

## A_pullback (touch, atr5, r1): where it does better or worse

Net R per trade. Measured on both periods; nothing here was used to pick the variant.

### train

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2016 | 28.0 | 0.607 | 0.208 | 5.830 |
| 2017 | 13.0 | 0.615 | 0.251 | 3.258 |
| 2018 | 50.0 | 0.520 | 0.031 | 1.573 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 33.0 | 0.576 | 0.143 | 4.731 |
| London | 24.0 | 0.708 | 0.425 | 10.2 |
| New York | 34.0 | 0.441 | -0.126 | -4.277 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 28.0 | 0.607 | 0.208 | 5.826 |
| low | 38.0 | 0.658 | 0.309 | 11.8 |
| normal | 25.0 | 0.360 | -0.277 | -6.921 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 40.0 | 0.550 | 0.101 | 4.024 |
| contradict | 13.0 | 0.538 | 0.069 | 0.893 |
| neutral | 38.0 | 0.579 | 0.151 | 5.745 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 23.0 | 0.652 | 0.299 | 6.877 |
| neutral | 38.0 | 0.579 | 0.151 | 5.724 |
| with trend | 30.0 | 0.467 | -0.065 | -1.939 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 30.0 | -0.065 | 61.0 | 0.207 | -0.271 |
| recent_bos | 13.0 | 0.379 | 78.0 | 0.074 | 0.305 |
| room | 37.0 | 0.236 | 54.0 | 0.035 | 0.201 |
| sweep_recent | 2.000 | -0.006 | 89.0 | 0.120 | -0.126 |
| rejection_recent | 20.0 | 0.193 | 71.0 | 0.096 | 0.097 |
| volume | 68.0 | 0.175 | 23.0 | -0.054 | 0.229 |
| killzone | 58.0 | 0.102 | 33.0 | 0.143 | -0.041 |
| score_75 | 0.000 | – | 91.0 | 0.117 | – |

### val

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2019 | 25.0 | 0.360 | -0.292 | -7.299 |
| 2020 | 26.0 | 0.462 | -0.082 | -2.125 |
| 2021 | 20.0 | 0.500 | -0.006 | -0.118 |
| 2022 | 22.0 | 0.591 | 0.178 | 3.914 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 26.0 | 0.462 | -0.084 | -2.179 |
| London | 26.0 | 0.423 | -0.162 | -4.215 |
| New York | 41.0 | 0.512 | 0.019 | 0.767 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 63.0 | 0.492 | -0.021 | -1.324 |
| low | 16.0 | 0.312 | -0.389 | -6.224 |
| normal | 14.0 | 0.571 | 0.137 | 1.921 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 47.0 | 0.447 | -0.113 | -5.315 |
| contradict | 16.0 | 0.625 | 0.246 | 3.933 |
| neutral | 30.0 | 0.433 | -0.142 | -4.245 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 28.0 | 0.357 | -0.293 | -8.201 |
| neutral | 34.0 | 0.588 | 0.170 | 5.775 |
| with trend | 31.0 | 0.452 | -0.103 | -3.201 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 31.0 | -0.103 | 62.0 | -0.039 | -0.064 |
| recent_bos | 15.0 | -0.208 | 78.0 | -0.032 | -0.176 |
| room | 57.0 | 0.011 | 36.0 | -0.173 | 0.184 |
| sweep_recent | 2.000 | -0.006 | 91.0 | -0.062 | 0.056 |
| rejection_recent | 20.0 | -0.004 | 73.0 | -0.076 | 0.072 |
| volume | 56.0 | -0.114 | 37.0 | 0.021 | -0.135 |
| killzone | 67.0 | -0.051 | 26.0 | -0.084 | 0.032 |
| score_75 | 0.000 | – | 93.0 | -0.061 | – |

## B_flip (touch, atr2, r0.75): where it does better or worse

Net R per trade. Measured on both periods; nothing here was used to pick the variant.

### train

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2016 | 21.0 | 0.667 | 0.163 | 3.414 |
| 2017 | 5.000 | 0.400 | -0.323 | -1.614 |
| 2018 | 24.0 | 0.583 | 0.004 | 0.088 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 18.0 | 0.556 | -0.046 | -0.836 |
| London | 13.0 | 0.692 | 0.200 | 2.597 |
| New York | 19.0 | 0.579 | 0.007 | 0.127 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 21.0 | 0.667 | 0.163 | 3.414 |
| low | 18.0 | 0.667 | 0.152 | 2.745 |
| normal | 11.0 | 0.364 | -0.388 | -4.270 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 26.0 | 0.615 | 0.068 | 1.766 |
| contradict | 6.000 | 0.833 | 0.452 | 2.714 |
| neutral | 18.0 | 0.500 | -0.144 | -2.592 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 1.000 | 0.000 | -1.051 | -1.051 |
| neutral | 20.0 | 0.750 | 0.302 | 6.040 |
| with trend | 29.0 | 0.517 | -0.107 | -3.101 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 29.0 | -0.107 | 21.0 | 0.238 | -0.345 |
| recent_bos | 16.0 | -0.254 | 34.0 | 0.175 | -0.429 |
| room | 22.0 | -0.056 | 28.0 | 0.111 | -0.167 |
| sweep_recent | 1.000 | -1.051 | 49.0 | 0.060 | -1.111 |
| rejection_recent | 16.0 | -0.032 | 34.0 | 0.071 | -0.103 |
| volume | 47.0 | 0.030 | 3.000 | 0.156 | -0.126 |
| killzone | 32.0 | 0.085 | 18.0 | -0.046 | 0.132 |
| score_75 | 5.000 | -1.031 | 45.0 | 0.157 | -1.188 |

### val

**By year**

| year | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| 2019 | 8.000 | 0.250 | -0.603 | -4.827 |
| 2020 | 15.0 | 0.467 | -0.197 | -2.950 |
| 2021 | 9.000 | 0.556 | -0.045 | -0.401 |
| 2022 | 17.0 | 0.706 | 0.226 | 3.849 |

**By session (signal candle)**

| session | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| Asia / off-hours | 13.0 | 0.385 | -0.351 | -4.557 |
| London | 14.0 | 0.643 | 0.110 | 1.538 |
| New York | 22.0 | 0.545 | -0.060 | -1.310 |

**By volatility regime (daily ATR %, train terciles)**

| vol_regime | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| high | 38.0 | 0.605 | 0.047 | 1.804 |
| low | 5.000 | 0.000 | -1.057 | -5.286 |
| normal | 6.000 | 0.500 | -0.141 | -0.847 |

**By 1H context**

| h1_context | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| confirm | 27.0 | 0.593 | 0.023 | 0.628 |
| contradict | 5.000 | 0.200 | -0.675 | -3.377 |
| neutral | 17.0 | 0.529 | -0.093 | -1.579 |

**By 15m bias at the signal**

| m15_bias | trades | win_rate | avg_R | total_R |
|---|---|---|---|---|
| against (pullback) | 3.000 | 0.333 | -0.450 | -1.351 |
| neutral | 18.0 | 0.556 | -0.039 | -0.707 |
| with trend | 28.0 | 0.536 | -0.081 | -2.271 |

**GSE confluence checks: trades with the check against trades without**

| check | trades_with | avg_R_with | trades_without | avg_R_without | difference |
|---|---|---|---|---|---|
| bias | 28.0 | -0.081 | 21.0 | -0.098 | 0.017 |
| recent_bos | 15.0 | 0.037 | 34.0 | -0.144 | 0.181 |
| room | 24.0 | 0.077 | 25.0 | -0.247 | 0.324 |
| sweep_recent | 0.000 | – | 49.0 | -0.088 | – |
| rejection_recent | 13.0 | 0.065 | 36.0 | -0.144 | 0.209 |
| volume | 45.0 | -0.043 | 4.000 | -0.601 | 0.558 |
| killzone | 36.0 | 0.006 | 13.0 | -0.351 | 0.357 |
| score_75 | 3.000 | -0.439 | 46.0 | -0.065 | -0.373 |

## Conclusion

**Neither setup passes validation.** The variant training picked for each setup did not make money after costs on 2019–2022 with enough evidence.

## Limitations

- Trend from GSE's bias on 1D and 4H; other trend definitions could differ.
- One trade at a time per variant; a trade open blocks later signals.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
