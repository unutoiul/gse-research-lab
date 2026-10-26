# F2 — Forward test: paper trades of the best S5 settings

Candles from **2026-10-23** to **2026-10-26 11:30:00+00:00** (OANDA M15). Frozen rules: `results/F2/rule.json`. Each setting needs 100 closed trades for a verdict (pass: profit after costs, profit factor ≥ 1.2, 90% interval above zero).

Git `b8925a6415`

## Running tally (after OANDA spread and 0.10 slippage)

| setup | trigger | stop | target | closed_trades | open | win_rate | avg_R | total_R | profit_factor | max_drawdown_R | gross_avg_R | ci_low | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pullback | touch | atr5 | r0.5 | 0 | 0 | – | – | 0.000 | – | 0.000 | – | – | running |
| A_pullback | touch | atr5 | r1 | 0 | 0 | – | – | 0.000 | – | 0.000 | – | – | running |
| B_flip | touch | atr2 | r0.75 | 0 | 0 | – | – | 0.000 | – | 0.000 | – | – | running |

## Every paper trade

No closed trade yet.

## For comparison: S5 on 2019–2022 (validation)

A_pullback touch 5 ATR 0.5 R: −0.040 R per trade (64% wins). A_pullback touch 5 ATR 1 R: −0.061 R (47%). B_flip touch 2 ATR 0.75 R: −0.088 R (53%).
