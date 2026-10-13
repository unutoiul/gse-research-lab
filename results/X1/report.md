# X1 — locked test result: WEAK

> PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified (`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.

Rule frozen 2026-10-13 (PREREGISTRATION.md, rule.json). Test period 2023-01-01 to 2026-10-01, opened once. The recorded validation result was reproduced exactly first.

Git `45cd076fc8` · dataset `a637520850ec…`

## Result (OANDA costs)

| Period | Trades | Expectancy (R) | Profit factor | Win rate |
|---|---|---|---|---|
| Train 2016–2018 | 118 | -0.096 | – | – |
| Validation 2019–2022 | 127 | 0.155 | – | – |
| **Test 2023–2026** | 121 | 0.101 | 1.224 | 0.562 |

Test, other cost levels: half spread 0.112 R, before costs 0.123 R. 90% interval of the net expectancy: -0.046 to 0.261 R. Max drawdown 9.571 R.

By year (net, R per trade): 2023 -0.182, 2024 0.257, 2025 0.232, 2026 0.236.

## Frozen criteria

- ✔ trades >= 100
- ✔ net expectancy > 0
- ✘ bootstrap lower bound > 0
- ✔ profit factor >= 1.2
- ✔ positive in >= 3 of 4 years

**WEAK.** Positive on the unseen years, but not by every frozen criterion: not evidence of an edge.

The test period is now spent: no other rule can be judged on it.
