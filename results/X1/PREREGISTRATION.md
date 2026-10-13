# X1 — one-shot test of a frozen rule on the locked test period

Frozen 2026-10-13, before the test period was opened. The owner approved opening
2023+ once for this rule. Machine-readable copy: `rule.json`.

## The rule (GSE Strategy v4.0 research variant, Malaysian SnR levels)

- 15m chart, swing lookback 10; fresh A/V levels and flipped levels ("both").
- Entry: after the first touch of such a level, if the candle closes back on the
  level's side, a market order at the next open ("close_back").
- Direction: against the 4H direction, and only when GSE's 1D bias agrees with the
  trade (a pullback against the 4H in the daily direction).
- London or New York session only. No sweep, discount/premium or MTF filter.
- Stop 5 chart ATR (15m) from the entry; target 1 times that risk.

## Where it came from

The best validation result in study S2 (rank 1 of 5,064 combinations with enough
trades): 127 trades, +0.155 R on 2019–2022, positive in all four years. It lost on
training: 118 trades, −0.096 R on 2016–2018. It was picked by looking at validation,
so validation is not evidence for it. Only the test period can be.

## The test

- Period: 2023-01-01 to 2026-10-01 (by candle close time), never used before.
- First, the same code must reproduce the recorded validation result exactly
  (127 trades, +0.1555 R); otherwise the test is not run.
- One run. No change to the rule, costs or criteria afterwards.

## Pass criteria (OANDA costs: bid/ask + 0.10 slippage on stops)

| Outcome | Condition |
|---|---|
| Inconclusive | fewer than 100 closed trades |
| Fail | net expectancy ≤ 0 |
| Pass | net expectancy > 0, 90% bootstrap lower bound > 0, profit factor ≥ 1.2, positive in ≥ 3 of 2023 / 2024 / 2025 / 2026 |
| Weak | net expectancy > 0, any pass condition missing |

A pass makes the rule a candidate, not a trading system: the TradingView parity
check and live paper trading would come next. After this run the test period is
spent: no other rule can be judged on it.
