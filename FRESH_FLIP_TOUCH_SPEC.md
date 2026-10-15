# Fresh and flipped level touches (GSE v4.1): rules and a backtest plan

This file writes down, from the v4.1 Pine source, exactly when GSE says a 15m, 1H or 4H chart is **touching a fresh level** or **touching a flipped level**, and turns that into a strategy that can be backtested. Nothing here has been backtested yet.

Sources (in `gse-website/tradingview/gse_4.1/src/`):

- `core.pine`: how levels are born, touched, broken and flipped
- `alerts.pine`: when touch, flip and reaction alerts fire
- `messages.pine`: the alert text
- `context.pine`: the confluence score and storyline
- `strategy*.pine`: the existing GSE Strategy v4.1 (15m fresh touch + 4H)

Defaults used below: swing lookback 10, 8 levels per side, ATR = ATR(14) of the chart, merging nearby levels off.

---

## 1. Reading the alert

```
GSE v4.1 | XAUUSD 15m | Fresh resistance touched (live)
Level 4159.62. First return to this level. A touch alone does not confirm a bounce or an entry.
Live price 4159.56 | Bias: Strong Bullish ▲▲
Support: 4133.02 (Touched) | Resistance: 4159.62 (Fresh)
Confluence: Bearish 38/100 Weak · Structure ○ · Location ◐ · Confirmation ○ · Timing ●
Story: ▲ At Resistance
```

| Part | Meaning |
|---|---|
| `Fresh resistance touched` | A 15m resistance level that nothing had touched since it formed was reached. This happens only once per level: after it, the level is "touched", no longer fresh. |
| `(live)` | Touch Timing is **Immediate**: it fired inside the candle, the moment the high reached 4159.62. The candle had not closed yet. It may still close above the level and break it. |
| `Bias: Strong Bullish ▲▲` | The 15m chart bias (swings + EMA 20/50 + last break) is +2 or more. So this is a **resistance touch against a strong bullish chart**. |
| `Confluence: Bearish 38/100` | The score for the side the event favours (resistance → short). 38 = Structure 0 + Location 28 + Confirmation 0 + Timing 10. |
| Structure ○ | 0 of 3: the bias is not bearish, there was no bearish BOS in the last 15 bars, and the latest swings are not LH/LL. With 0 structure the score is **capped** at 60. |
| Location ◐ | 2.8 of 3: resistance within 1 ATR (1), the level is fresh (0.8), and at least 2 ATR of room to the first support below (1). |
| Confirmation ○ | No sweep, rejection candle or volume spike in the last 8 bars. |
| Timing ● | London or New York session. |
| `Story: ▲ At Resistance` | The last structure break was bullish and the nearest resistance is within 1 ATR. |

In short: a good location (first touch of a fresh level) with **no** supporting structure. GSE itself says a touch is not an entry.

---

## 2. How a level is made

Each chart builds its own levels from its own candles. A 4H level comes from 4H candles, a 15m level from 15m candles.

1. **Birth.** An **A level** (resistance) is a confirmed pivot high of the candle *bodies* (`max(open, close)`) with 10 bars on each side. A **V level** (support) is a pivot low of `min(open, close)`. GSE knows about the pivot only 10 bars after it, at that bar's close.
2. **Checked on arrival.** Over those 10 bars:
   - if any close went through the level, it is never created;
   - if price came back to it (a candle reaching the level after one that did not), it starts as **touched**, not fresh.
3. **Limit.** At most 8 levels per side are kept. The one that has held its current role the longest is dropped first.
4. Price is the body price (open or close), not the wick. The level also stores its outermost wick (used for the stop).

### States

| State | Meaning |
|---|---|
| **Fresh** | Nothing has touched it since it formed. |
| **Touched** | Price has come back at least once. |
| **Flip candidate** | Broken decisively; now waiting on the other side for a retest. Not alerted, not used for confluence. |
| **Flipped** | A candidate that was retested and held from the new side. Old resistance is now support, or the reverse. |

A **touch** is a candle whose range contains the level: `low <= price <= high`. Candles sitting on the level one after another count as **one** visit. A new visit needs a candle that does not reach the level first.

---

## 3. The level lifecycle (at each candle close)

For a resistance level at price `P` (support is the mirror image):

1. **Close above `P`: broken.**
   - It becomes a **flip candidate** (now support) only if all of these hold:
     - flips are enabled;
     - it is not already a flipped level;
     - it has been touched at least once (`touches >= 1`);
     - the break is **decisive**: the close is at least `0.1 ATR` above `P`, the candle is bullish, and its body is at least half its range.
   - Otherwise the level is **removed**.
   - So a fresh level broken on its first touch is removed. It never flips.
2. **Range contains `P`, close at or below `P`: a touch.** On a new visit, `touches += 1`. A fresh level becomes **touched** (event `level_tap_res`).

### Flip candidate → flipped (v4.1 role-reversal rules)

For a candidate that was resistance and is now support:

1. **Expiry.** It is removed after 20 bars without confirmation.
2. **Failed flip.** A close below `P − 0.1 ATR` (back through, by more than the buffer) is a **failed flip**: the level is removed and the `flip_failed_bear` alert fires. A close back through by less than the buffer is ignored.
3. **Move away first.** A return counts as the retest only after price has gone at least **1 ATR beyond `P`** (high − P) since the break.
4. **Confirmation.** The retest candle must reach `P` and close above `P`, with either:
   - a bullish candle, or
   - a lower wick of at least 35% of its range.

   Then the level becomes **flipped support** with `touches = 1`. The `flip_to_support` alert fires at that close.
5. **Later life.**
   - Every new visit to a flipped level adds a touch. It stays "flipped".
   - A close through a flipped level removes it. It cannot flip again.
   - Only a just-confirmed flip (`touches <= 1`) gets the top location score (1.0). Once touched again it scores 0.

---

## 4. When the touch alerts fire

At every candle close GSE takes a **watch list**: the fresh, touched and flipped levels that the closing candle did **not** reach. Flip candidates are left out. A level born at this close is watched from the next candle.

| Event | Immediate timing (default, `(live)`) | Candle close timing |
|---|---|---|
| **Fresh support/resistance touched** | During the candle, the first time price reaches a level that was fresh in the watch list. A gap over the level does not count. Fires even if the candle later closes through it. | At the close, if the candle reached the fresh level and did **not** close through it. |
| **Flipped support/resistance touched** | During the candle, the first time price reaches a flipped level in the watch list. | At the close, if the candle reached it and closed on its side (`close >= P` for support, `<= P` for resistance). |
| **Resistance flipped to support** (and the reverse) | — | At the close of the confirming retest (section 3). The first "flipped touched" alert comes on the **next** visit after this one. |
| **Failed flip** | — | At the close that goes back through a candidate. |
| **Rejection at fresh/touched/flipped level** | — | At the close: the candle reached the level, closed back on its side in the level's direction (bullish candle at support, bearish at resistance), and the rejection wick is at least 50% of the range. |

### OHLC version, for a backtest

For a watched level `P` with role `r` (+1 support, −1 resistance), on bar `t`:

- **in watch** = the state at the close of `t-1` is fresh or flipped, and bar `t-1` did not reach `P`
- **touch (Immediate)** = in watch, and `low[t] <= P <= high[t]`
- **touch (Candle close)** = touch (Immediate), and `r * (close[t] − P) >= 0`
- **broken on the touch bar** = `r * (close[t] − P) < 0`
- **rejection** =
  - support: touch, `close > P`, `close > open`, and `(min(open, close) − low) / (high − low) >= 0.5`
  - resistance: touch, `close < P`, `close < open`, and `(high − max(open, close)) / (high − low) >= 0.5`

### 15m, 1H and 4H

- Each timeframe is a separate chart with its own levels, ATR, bias and alerts.
- A 15m alert is about a 15m level. A 4H level touch is a 4H-chart alert, even though it can fire in the first minute of a 4H candle.
- Our data is M15 (OANDA). 1H and 4H candles are built from it with TradingView's session anchors (`gse_research/timeframes.py`). Building them this way also gives us **when** inside the 1H or 4H candle the touch happened:
  - freeze the 1H/4H watch list at that chart's close;
  - the touch time is the first M15 bar inside the next 1H/4H candle whose range reaches `P`.

  This matches Immediate timing and is needed for a limit entry on 1H/4H.

---

## 5. The strategy to backtest

GSE treats a touch as information, not a signal. The trade idea is the classic one:

- **fade the first touch** of a fresh level;
- **buy or sell the retest** of a confirmed flipped level.

Support → long, resistance → short.

### Base rule (one setting each, to start)

| Item | Rule |
|---|---|
| Market / data | XAU/USD. OANDA M15 bid/ask, 2016+ (the part that matches TradingView's gold session). |
| Charts | 15m, 1H and 4H, each run separately with its own levels. |
| Levels | GSE v4.1 defaults (section 2–3), lookback 10. |
| Trigger | **F**: the first touch of a fresh level. **X**: the first touch of a flipped level after its confirmation (`touches == 1` at the prior close). Each level trades at most once. |
| Direction | Long at support, short at resistance. |
| Entry | **Limit at `P`**, filled at the touch (Immediate timing). If the bar opens beyond `P`, fill at the open. |
| Stop | Beyond the level's stored wick by `max(tick, 0.2 ATR)`, the GSE website stop. No wick on record → no trade. |
| Target | Fixed **1.5R**. GSE's TP2 rule (≥ 1.5R, ≤ 8 ATR, not past the first major obstacle) is a variant. |
| Same-bar ambiguity | If one bar reaches both stop and target, count it as a stop. |
| Positions | One per chart at a time. A new signal while a trade is open is skipped. |
| Costs | Real bid/ask spread plus 0.10 slippage, as in R001. Report the result before costs too. |

### Variants (one at a time, each counts as a trial)

1. **Entry confirmation**
   - `close_back`: the touch candle closes back on the level's side → market at the next open.
   - `rejection`: the GSE rejection candle above → market at the next open.
2. **4H direction**: off / with / against the trade. Use the 4H swing-break direction from the GSE strategy, taken from the previous closed 4H candle.
3. **Chart bias**: the trade agrees with the chart bias, or opposes it. The alert in section 1 opposes it.
4. **Session**: London or New York only (the Timing ● check).
5. **Confluence**: the side's score is ≥ 60 or ≥ 75 at the touch.
6. **Stop**: 1, 1.5 or 3 ATR from `P` instead of the wick stop.
7. **Target**: 1R, 2R, or GSE TP2.
8. **Flip rules**:
   - the v4.1 defaults;
   - the v4.0 behaviour (min touches 0, decisive off, move away 0).

   This is the R003 experiment the v4.1 changelog names.
9. **Inducement**: off / present / cleared / swept (section 6).

Stops, targets and trailing are a separate layer (section 7).

### What to report

For each chart and trigger (F, X), split train (2016–18) and validation (2019–22):

- trades per year
- win rate
- average R net and gross
- profit factor
- maximum drawdown in R
- results by year, long and short separately
- the spread cost as a share of R

---

## 6. Inducement

**The idea (SMC).** Before price reaches the real level, it first takes out a smaller swing sitting in front of it. Early traders who bought that minor low (or sold that minor high) get stopped out. That liquidity is the "inducement". A level with inducement cleared in front of it is said to hold better than one price runs straight into.

GSE already had this as an option in its old strategy (`gse_4.1/audit/strategy-before-simplification/`, defaults: minor swing lookback 3, valid 10 bars). It was off by default and never measured. The rules below follow it, written for a long at support `P`. Shorts at resistance are the mirror image.

**Minor swing.** A confirmed **wick** pivot low with lookback 3, so it is known 3 bars later. Wicks, not bodies: inducement is about where stops sit.

**Eligible inducement for the level.** A minor swing low that:

- formed after the level was born;
- sits **above** `P`, between the level and price.

Only the most recent eligible minor low counts.

**Variants:**

| Variant | Condition at the close before the touch |
|---|---|
| `off` | No inducement rule. |
| `present` | An eligible minor low exists and has not been taken. Price still has to take it on the way to `P`. |
| `cleared` | An eligible minor low was traded through (`low < minor low`) on an earlier bar than the touch. Price came back to `P` in a later leg. |
| `swept` | GSE's old rule. In the last 10 bars, a candle went below an eligible minor low and closed back above it, and the candle's low stayed above `P`. |

**Not inducement:**

- the touch candle itself takes the minor low (price ran straight through to the level);
- the level has no eligible minor low at all.

Record these too: the comparison "with inducement vs without" is the actual test.

**No lookahead.**

- The condition is checked at a candle close. A limit order at `P` is placed only after it is met.
- A minor low is usable only once its 3 confirming bars have closed.
- For `close_back` and `rejection` entries, the sweep candle must come before the touch candle.

---

## 7. Stop loss, take profit and trailing

The test design matters more than any one stop or target choice. Keep the entry fixed and run every exit model on **the same list of entries**. Then the exits are compared on identical trades, and adding an exit model costs seconds, not a new structure run.

### Stops (initial risk = 1R)

| Code | Stop | Note |
|---|---|---|
| `S-wick` | The level's wick + `max(tick, 0.2 ATR)` | GSE's website stop. Often within two spreads on 15m: costs then eat most of R. |
| `S-wick-floor` | `S-wick`, but at least 1 ATR from entry | GSE's old minimum-stop rule (1 ATR). Recommended default. |
| `S-atr` | 1, 1.5 or 3 ATR from entry | Ignores the level. Earlier studies: wider stops lose less, but have not turned a loss into a profit. |

### Targets

| Code | Target |
|---|---|
| `T-R` | Fixed 1R, 1.5R or 2R. |
| `T-obstacle` | The first opposing level, equal highs/lows or previous day/week, minus `max(tick, 0.1 ATR)` (RXM-1). Skip the trade if it is under 1R away. |
| `T-tp2` | GSE TP2: the best target ≥ 1.5R and ≤ 8 ATR, not past the first major H1/H4/daily/weekly obstacle. |
| `T-time` | No target. Exit at the close after N bars (16 = GSE's horizon). |

### Trade management (on top of a stop and target)

| Code | Rule |
|---|---|
| `M-none` | The initial bracket stays as it is. |
| `M-be` | At +1R, move the stop to entry plus the spread. |
| `M-atr-trail` | At +1R, trail the stop 2 ATR behind the best close since entry. No fixed target, or a far one (4R). |
| `M-swing-trail` | At +1R, move the stop under each new confirmed minor swing low (lookback 3). This is the SMC-style trail. |
| `M-partial` | Close half at 1R and move the stop to entry. Trail the rest with `M-swing-trail`. R is counted on the full position. |

### Simulation rules (all exits)

- Fills use OANDA bid/ask candles: longs buy the ask and exit on the bid. Add 0.10 slippage to market orders and stops.
- A candle that opens beyond the stop or target exits at the open.
- A candle that reaches both stop and target counts as a stop.
- A trailing stop is updated **at a candle close** and applies from the next candle. It never uses the same candle's high or low.
- Every trade also records its MFE and MAE, in R and in ATR.

### Which exit is "best"

Exit choice depends on what price does after the touch:

| What the MFE distribution shows | What it means |
|---|---|
| Median MFE under 1R | No stop, target or trail can make money; price does not move far enough. |
| Most trades reach about 1R, few go further | A fixed target fits; trailing gives profit back. |
| A long right tail (some trades run 3R and more) | Trailing or structure targets fit. |

So decide the exit **from data on the training years**. Do not try every combination and keep the best one: with this many choices, a winner on training data is expected by chance. S1 and S2 found exactly this.

---

## 8. How to run many backtests

Run in three steps. Each step decides whether the next one is worth running.

**Step 1. Port (code + checks).**

- Add the four v4.1 flip rules, the watch-list touch logic (section 4) and inducement (section 6) to `gse_research/structure.py`.
- Check the port against the Pine with the existing tests.
- Output: one table of **every touch event**, with columns:
  - chart, time, level id, state (fresh or flipped), side;
  - inducement status;
  - bias, 4H direction, session and confluence at the prior close.

**Step 2. Event study (is there any edge, before choosing exits).**

- Use train 2016–18 only, with no costs.
- For each cell, look 4, 8, 16 and 32 bars ahead and record MFE/MAE in ATR, plus the share that reach +1R before −1R (with the `S-wick-floor` stop).
- Cells: chart (15m, 1H, 4H) × trigger (fresh, flipped) × inducement (off, present, cleared, swept, none). That is 30 cells.
- Compare each cell with a baseline: random entries in the same direction at similar times.
- If no cell clearly beats the baseline before costs, stop here. No exit model will fix it.

**Step 3. Strategy grid (only for cells that pass step 2).**

- Grid: entries (limit, close_back) × at most about 12 exit models from section 7.
- Fix the list of models and the number of trials **before** running. That is the trial budget.
- Train picks, validation 2019–22 judges once. Use the same verdict rules as S1/S2: expectancy after costs, confidence interval, years positive, and the luck line for the number of trials.

**Where it runs.**

- The same way as S1/S2: a study module in `gse_research/`, dispatched from the admin Research tab to GitHub Actions.
- One run per study, about 30 minutes. The structure is computed once per chart, then every variant is scored on the same events.
- A new job kind needs adding to the Neon constraint, which needs your approval, as for `search_s1`.

---

## Results so far (2026-10-15)

- **S3** ([results/S3/report.md](results/S3/report.md)): the full search, 86,184 combinations (section 8 in one run), on GitHub Actions.
  - **No combination passes validation.** The best training SQN (1.33) is far below the luck line (4.4). Of the top 20 on training, 19 lose on 2019–22, and the 20th makes +0.005 R.
  - **Inducement does not help.** Against no inducement, everything else equal, every setting changes the result by at most ±0.06 R per trade, and improves only about half the pairs. "Present" (price runs straight into the level) is slightly worse.
  - **Wider stops lose less** (3 ATR −0.13 R, against 1 ATR −0.32 R on validation), as in O3, S1 and S2. Trailing and fixed targets are about the same.
- **E1** ([results/E1/report.md](results/E1/report.md)): the edge check from section 8, step 2. First touches against random levels on the same side, at the same distance from price, before costs.
  - **No edge in any of the 18 cells** (chart × lookback × fresh/flipped). The measure: does price get 1 ATR away from the level before 1 ATR through it?
  - **Fresh levels behave like random prices** at every lookback. On 15m the difference is within ±0.025.
  - **Flipped levels on 15m** do slightly better than random in both periods at every lookback (+0.02 to +0.065), but no interval excludes zero.
  - **Costs are the bigger problem.** One spread plus slippage is about 0.3 ATR on 15m, 0.14 on 1H and 0.07 on 4H. A 1:1 trade with a 1 ATR stop needs about 65% wins on 15m to break even; touches give 43–53%.
- **O4** ([results/O4/report.md](results/O4/report.md)): the 15m strategy as written, with lookbacks 8/10/12 × H4 6/8/10. All nine lose about −0.9 R after costs and −0.15 to −0.27 R before costs. The v4.1 flip rules change almost nothing against v4.0 (O2).

---

## 9. Before running it

- **Much of trigger F has been tested already** (v4.0 levels; fresh levels are the same in v4.1). The results are in `results/`:
  - 15m and 1H fresh touches with or against 4H, with limit, rejection and close-back entries, lost money on train;
  - S1/S2 searched Malaysian SnR fresh levels with confluences and stops/targets: nothing passed validation;
  - X1 (15m, close-back, against 4H with the 1D storyline, 5 ATR stop, 1R target) was WEAK on 2023+: +0.10R, with an interval that reaches below zero.

  Re-running F mostly re-tests these.
- **Trigger X (confirmed flipped levels under the v4.1 rules) has not been tested.**
  - `gse_research/structure.py` is a v4.0 port. Its flips have no minimum touches, no decisive break, no move-away and no failed flips.
  - Its strategy option `level_type="flip"` trades the *candidate*, before any retest. That is not GSE's flipped level.

  Porting the four v4.1 rules (section 3) and the `in_contact` watch logic (section 4) comes first, with checks against the Pine.
- **No clean holdout is left.** 2023+ was spent on X1. Fix the rule and the number of variants before looking at validation. Anything that passes should then be forward-tested on data after 2026-10-13, or on TradingView alerts as they arrive.
