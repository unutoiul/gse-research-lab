# O4 — GSE Strategy v4.1 lookbacks (15m entries with H1 targets × H4 direction)

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

The strategy as written (fresh-touch limit with the 4H direction, website stop and TP2), with v4.1's level engine. 15m/H1 swing lookback [8, 10, 12] × H4 swing lookback [6, 8, 10]: nine settings fixed before any result. Train 2016–2018, validation 2019–2022 (2023+ was spent on X1). Costs: **net** = OANDA bid/ask + 0.10 slippage on stops; **gross** = mid prices, no slippage. Conservative intrabar order.

Git `62346adfab` · dataset `a637520850ec…`

## All nine settings

| swing_len | h4_swing_len | train_net_trades | train_net_win_rate | train_net_expectancy_R | train_net_profit_factor | train_net_max_drawdown_R | train_gross_expectancy_R | val_net_trades | val_net_win_rate | val_net_expectancy_R | val_net_profit_factor | val_net_max_drawdown_R | val_gross_expectancy_R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 6.000 | 523.0 | 0.031 | -0.988 | 0.192 | 516.7 | -0.036 | 803.0 | 0.040 | -0.918 | 0.199 | 737.4 | -0.152 |
| 8 | 8.000 | 512.0 | 0.029 | -1.025 | 0.171 | 525.0 | -0.029 | 831.0 | 0.040 | -0.906 | 0.211 | 752.8 | -0.192 |
| 8 | 10.0 | 532.0 | 0.023 | -1.080 | 0.131 | 574.8 | -0.072 | 831.0 | 0.042 | -0.870 | 0.239 | 723.4 | -0.219 |
| 10 | 6.000 | 411.0 | 0.029 | -0.989 | 0.191 | 406.4 | 0.062 | 651.0 | 0.041 | -0.874 | 0.233 | 568.7 | -0.152 |
| 10 | 8.000 | 404.0 | 0.030 | -0.982 | 0.195 | 396.6 | 0.065 | 664.0 | 0.041 | -0.880 | 0.228 | 584.4 | -0.159 |
| 10 | 10.0 | 419.0 | 0.021 | -1.052 | 0.142 | 440.7 | 0.023 | 663.0 | 0.044 | -0.859 | 0.245 | 569.2 | -0.208 |
| 12 | 6.000 | 339.0 | 0.027 | -1.027 | 0.163 | 348.1 | 0.030 | 532.0 | 0.038 | -0.903 | 0.208 | 480.5 | -0.219 |
| 12 | 8.000 | 342.0 | 0.026 | -1.028 | 0.162 | 351.7 | 0.065 | 542.0 | 0.037 | -0.909 | 0.202 | 496.1 | -0.175 |
| 12 | 10.0 | 359.0 | 0.019 | -1.103 | 0.105 | 395.9 | -0.018 | 535.0 | 0.039 | -0.890 | 0.217 | 479.3 | -0.275 |

## Net R per trade by year (train 2016–2018, validation 2019–2022)

| swing_len | h4_swing_len | train_net_2016_R | train_net_2017_R | train_net_2018_R | val_net_2019_R | val_net_2020_R | val_net_2021_R | val_net_2022_R |
|---|---|---|---|---|---|---|---|---|
| 8 | 6.000 | -0.870 | -0.991 | -1.085 | -1.213 | -0.832 | -0.889 | -0.748 |
| 8 | 8.000 | -0.871 | -0.994 | -1.201 | -1.218 | -0.760 | -0.855 | -0.768 |
| 8 | 10.0 | -0.989 | -1.039 | -1.202 | -1.177 | -0.706 | -0.840 | -0.738 |
| 10 | 6.000 | -0.758 | -0.953 | -1.205 | -1.095 | -0.741 | -0.980 | -0.691 |
| 10 | 8.000 | -0.768 | -0.957 | -1.200 | -1.102 | -0.744 | -0.979 | -0.688 |
| 10 | 10.0 | -0.913 | -1.015 | -1.203 | -1.189 | -0.623 | -0.943 | -0.674 |
| 12 | 6.000 | -0.862 | -0.990 | -1.187 | -1.255 | -0.805 | -0.954 | -0.612 |
| 12 | 8.000 | -0.873 | -1.004 | -1.184 | -1.246 | -0.812 | -0.956 | -0.608 |
| 12 | 10.0 | -1.048 | -1.051 | -1.191 | -1.247 | -0.804 | -0.943 | -0.562 |

## Validation net expectancy (R): rows 15m/H1 lookback, columns H4 lookback

| chart \ H4 | 6 | 8 | 10 |
|---|---|---|---|
| 8 | -0.920 | -0.910 | -0.870 |
| 10 | -0.870 | -0.880 | -0.860 |
| 12 | -0.900 | -0.910 | -0.890 |

## Validation gross expectancy (R), before any cost

| chart \ H4 | 6 | 8 | 10 |
|---|---|---|---|
| 8 | -0.150 | -0.190 | -0.220 |
| 10 | -0.150 | -0.160 | -0.210 |
| 12 | -0.220 | -0.170 | -0.270 |

## Against v4.0's levels (study O2, same settings)

| swing_len | h4_swing_len | train_net_expectancy_R_v41 | val_net_expectancy_R_v41 | val_gross_expectancy_R_v41 | train_net_expectancy_R_v40 | val_net_expectancy_R_v40 | val_gross_expectancy_R_v40 |
|---|---|---|---|---|---|---|---|
| 8 | 6.000 | -0.988 | -0.918 | -0.152 | -0.967 | -0.917 | -0.149 |
| 8 | 8.000 | -1.025 | -0.906 | -0.192 | -1.005 | -0.904 | -0.186 |
| 8 | 10.0 | -1.080 | -0.870 | -0.219 | -1.062 | -0.863 | -0.224 |
| 10 | 6.000 | -0.989 | -0.874 | -0.152 | -0.967 | -0.897 | -0.151 |
| 10 | 8.000 | -0.982 | -0.880 | -0.159 | -0.959 | -0.905 | -0.165 |
| 10 | 10.0 | -1.052 | -0.859 | -0.208 | -1.030 | -0.858 | -0.192 |
| 12 | 6.000 | -1.027 | -0.903 | -0.219 | -1.028 | -0.898 | -0.191 |
| 12 | 8.000 | -1.028 | -0.909 | -0.175 | -1.027 | -0.901 | -0.152 |
| 12 | 10.0 | -1.103 | -0.890 | -0.275 | -1.101 | -0.872 | -0.243 |

## Conclusion

Best on train: 10 / 8, train net -0.982 R, validation net -0.880 R on 664 trades. 0 of 9 settings are positive on validation after costs.

## Limitations

- Nine settings; the best training result is optimistic by construction.
- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).
