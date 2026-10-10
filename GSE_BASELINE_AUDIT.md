# GSE Baseline Audit: GSE v4.0

Date: 2026-10-10 · Phase 1 of the GSE Engineering Research plan · Read-only: no baseline file was modified.

This document records what the code **actually does**, with file and line references. Where earlier documents (`AUDIT.md`, `README.md`, `BACKTEST.md`, guides) disagree with the code, the code wins and the disagreement is listed in section 9.

**Verification status.** A first draft was written earlier on 2026-10-10. In a second pass the same day, every definition in sections 1–9 was re-read against the source files cited, and the test suites were re-run. Corrections and additions from that pass are listed in Appendix A. Section 10 is different: it reports observations from the first session that could not be re-checked from the repository.

## 0. Scope, sources and fingerprints

**Baseline: GSE v4.0.** The brief names v4.0 as the baseline for the audit (Phase 1) and the reproduction (Phase 4), and the production webhook feed sends `"ver":"4.0"` payloads. v2.3 is described only as a reference, in section 8.

Repository audited: `gse-website` at commit `19564ee` (2026-10-10 13:39 +0700), working tree clean. GSE v4.0 is in two codebases. The **Pine indicator** produces the evidence. The **website** (TypeScript) decides the Early / Core / A+ setup stages. Both are audited here, because the A+ qualification exists only on the website.

| Component | File | SHA-256 |
|---|---|---|
| Live indicator (generated, pasted into TradingView) | `tradingview/gse_4.0/GoldStructureEngine_4.0.pine` (1,997 lines) | `2df7b96ac7152e42a2c902d21becc184389f4175b87ca11f59325163287307fd` |
| Indicator source parts (joined by `build.mjs`, in this order) | `tradingview/gse_4.0/src/{core,context,inputs,indicator-defaults,indicator-inputs,engine,analysis,mtf,indicator,messages,alerts}.pine` | `build.mjs --check`: generated file matches the parts |
| Research strategy (separate execution model) | `tradingview/gse_4.0/GoldStructureEngineStrategy_4.0.pine` (964 lines) | `a32e6642f70db720a63cef11d4d0aa43ccb4ea0c2e35edf4611d845377fb3c15` |
| v2.3 indicator (reference) | `tradingview/gse_2.3/GoldStructureEngine_2.3.pine` | `0a38a3c70c73238a8be928ac71c4f5a4706ceb672f056d516a4f848c501c8297` |
| Website GSE setups engine | `api/_lib/gseSetups.ts` | `a228b8ea04ec764a98e832e12bdbf3bfe44fe09cc894c0e8a76a301968aed6ee` |
| Website setup policy | `api/_lib/gseSetupPolicy.ts` (`setup-v1`) | `008ed924cffcc687b55124bdce6a17156739c25af8a269d9128211a219a1362d` |

**Dependencies.** The indicator is standalone: no Pine libraries and no imports. It makes `request.security` calls to the same symbol at D, W and M (`engine.pine`) and at 4H, 1H and 15m (`mtf.pine`). The website setups engine depends on `gseSetupPolicy.ts`, `websiteReasons.ts` (`READ_RULES`) and `websiteTargetEngine.ts` (`bufferAtr`). The strategy reuses `core.pine` and `engine.pine` and adds its own `strategy-*.pine` parts.

Existing automated checks, re-run 2026-10-10 on Node 22.20, all passing: `build.mjs --check` (both generated files match their parts), `test-core.mjs` 33, `test-indicator.mjs` 85, `test-audit.mjs` 16, `test-strategy-targets.mjs` 551, `test-simple-strategy.mjs` 1,735, `test-alert-runtime.mjs` (exit 0, no summary line), `npm run test:gse-setups` 38. These are logic tests on synthetic candles. They are not Pine compilation, TradingView runtime or market-data tests, and **none of them emulates `ta.pivothigh` / `ta.pivotlow`** (see P1 in section 5.1).

In the rest of this document, `core:239` means `tradingview/gse_4.0/src/core.pine` line 239, and so on for the other `src` parts. Website paths are relative to `gse-website/`.

### 0.1 Coverage of the Phase 1 brief

| Brief item | Where |
|---|---|
| Locate the complete v4.0 source and its dependencies | Section 0 |
| Architecture, inputs, calculations | Sections 1, 1.1, 2 |
| SNR; freshness, touches, strength, invalidation | 3.1, 3.2 |
| BOS / CHoCH; sweeps and swings | 3.3, 3.4 |
| Role reversal | 3.5 |
| Higher-timeframe alignment | 3.7 |
| Displacement, volatility, opposing-level space | 3.8 |
| Scoring, setup qualification, A+ thresholds, storyline | 3.9–3.11, 3.14 |
| Alert conditions | 3.13 |
| Every condition that can reject a candidate | Section 4 |
| Repainting, look-ahead, leakage, duplicates, performance | Section 5 (5.1 for porting hazards) |

## 1. Architecture: where each decision is made

GSE v4.0 is split across three places. Research must keep them apart.

```
TradingView (Pine, one instance per chart: 15m, 1H, 4H)
  core.pine      levels, swings, BOS/CHoCH, liquidity, sweeps, bias, sessions
  context.pine   room, BOS recency, sweep pairing, confluence score, Golden Zone, storyline
  mtf.pine       4H / 1H / 15m bias readout (15m and lower charts only)
  alerts.pine    live and close events, Webhook JSON (schema gse.context.v1)
        │  webhook (admin feed "main")
        ▼
Website (TypeScript)
  websitePlanRules.ts   parser parseWebsiteEvidence, trade-plan proposals
  gseSetups.ts          GSE setups: Watching → Early → Core → A+ (setup-v1)
  websiteTargetEngine   stop/target geometry for plans
  websitePlans / JEV    model review, 60% approval, watchlist
```

- **The indicator has no entries, stops, targets or trade lifecycle.** `README.md` (4.0): "It contains no trade-plan state, entry/stop/target plots…". Its outputs are descriptive states and events.
- **Setup qualification (Early, Core, A+) is decided on the website**, from the indicator's evidence. That is the only "A+" in v4.0.
- **`GoldStructureEngineStrategy_4.0.pine` is a separate research execution model**: a fresh-level touch-limit entry with H4 direction and the website's stop/target engine (`FRESH_LEVEL_STRATEGY.md`). It is not the indicator's behaviour. There is no published backtest result for it (`BACKTEST.md`: "No historical performance study has been completed").

### 1.1 Order of operations on each candle

Pine calls `f_core_update` and then `f_context_update` on every update. Stored state changes only when the candle is confirmed (`engine:17` passes `barstate.isconfirmed`). The order matters, and a port must keep it:

1. ATR(14), EMA 20/50 and wick pivots. A new swing high or low shifts `ph1→ph2` or `pl1→pl2` and re-arms that side's swing sweep (`core:240-264`).
2. HH / LH / HL / LL from the last two swings (`core:266-270`).
3. Breaks against the **just-updated** `ph1` / `pl1`: bull first, then bear. `struct_dir` is updated after each (`core:272-285`).
4. Bias score (`core:287-292`).
5. Level maintenance over the existing levels: candidate expiry / removal / confirmation; flips, removals and touches of normal levels; `in_contact`. Then both roles are trimmed to the cap (`core:304-388`).
6. New body pivots, A first, then V: validity via `f_pivot_history`, then merge or add, then trim (`core:390-403`).
7. Nearest support / resistance and the closest-level distances. Flip candidates are excluded (`core:405-440`).
8. Prune the EQ reference pivots, then create pools from this candle's new wick pivots (`core:442-488`).
9. EQ pool sweeps and consumption (`core:490-516`).
10. Previous day / week references: consumption reset on a new day or week, then day / week sweeps (`core:518-554`).
11. Swing sweeps against `ph1` / `pl1` (`core:556-562`), then qualification (`core:565-569`) and sessions (`core:571-574`).
12. Context: bias ok → room obstacles → qualified-sweep clock → BOS recency → sweep–BOS pairing → at level → Golden Zone → conflict → level quality → rejection and volume → score and cap → storyline (`context:97-208`).

## 2. Inputs and fixed constants

User inputs that change analysis (`inputs.pine`). Display and alert switches in `indicator-inputs.pine` do not change calculations, except where noted.

| Input | Default | Effect | Ref |
|---|---|---|---|
| Swing Lookback | 10 (3–50) | Bars each side for wick swings (structure) and body pivots (levels); also used by the 4H/1H/15m readout | `inputs.pine:4` |
| Levels per Side | 8 (2–20) | Cap per role; the oldest by `born_bar` is trimmed | `:6` |
| Enable Flipped Levels | true | A close through a level makes it a flip candidate (otherwise removed) | `:7` |
| Merge Nearby Levels | false | Off: only exact-tick duplicates merge. On: a pivot within Zone Width of a same-role level merges into it | `:8` |
| Zone Width (ATR) | 0.5 | Merge distance when merging is on | `:9` |
| Equal H/L Tolerance (ATR) | 0.15 | Equal-high/low pool tolerance | `:11` |
| Follow Last Structure Break | true | Bias falls back to ±0.5 when swings oppose the last break | `:13` |
| Require Sweep for Golden Zone | false | Golden Zone needs a qualified pre-BOS sweep; also changes the confluence cap | `indicator-inputs.pine` (grp_setup) |
| Room to Next Obstacle (ATR) | 2.0 | Minimum room for Golden Zone and the confluence room check | `indicator-inputs.pine` (grp_setup) |
| Approach Distance (ATR) | 0.5 | Live approach alerts only | `indicator-inputs.pine` (grp_alert) |

Fixed constants (`indicator-defaults.pine:3-18`): flip wick 35%, flip candidate age 20 bars, BOS recency window 15 bars, sweep→BOS window 6 bars, sweep qualification distance 3.0 ATR, confirmation cluster 8 bars, rejection proximity 2.0 ATR, confluence weights 35/30/25/10, alert threshold 75, gate cap 60, stream id `main`. Hard-coded elsewhere: ATR(14), EMA 20/50, volume SMA(20) × 1.2, EQ pools ≤ 8 per side, EQ reference pivots ≤ 10 per side.

## 3. Definitions as implemented

### 3.1 Support and resistance (SNR levels)

- **Source:** confirmed **body** pivots. `a_lvl = ta.pivothigh(max(open, close), L, L)` is resistance (role −1, kind "A"); `v_lvl = ta.pivotlow(min(open, close), L, L)` is support (role 1, kind "V") (`core:297-300`). A pivot is known L bars after its origin bar.
- **Creation validity** (`f_pivot_history`, `core:200-211`): the pivot is rejected if any close since the origin went through it. The wick starts at the origin bar's low (support) or high (resistance) and extends to every later bar that reached the level. Touches during the L confirmation bars are counted: a later bar counts if the bar before it did not reach the level; the first bar after the origin counts only if it opened away from the level by more than half a tick (`f_opened_away`, `core:195-196`). A level with touches > 0 at birth starts as **touched**.
- **Merging** (`f_merge_into`, `core:175-191`; `f_level_duplicate`, `core:166-170`): the nearest same-role, non-candidate level within half a tick (or within Zone Width × ATR if merging is on) absorbs the new pivot. If that level was fresh, it becomes touched with touches + 1 ("the pivot is known swing-length bars late, too late for a touch alert").
- **Cap:** at most `zone_count` per role. `f_trim_role` (`core:154-162`) removes the level with the oldest `born_bar` until the cap holds. `born_bar` restarts when a level flips, so a just-broken level is the newest on its new side.
- **Structure versus levels:** structure uses **wick** pivots (`high`/`low`, `core:251-252`), levels use **body** pivots. They are different swing sets.

### 3.2 Freshness, touches, strength, invalidation

- **States** (`core:3-6`): 0 fresh, 1 touched ("tapped"), 2 flip candidate, 3 confirmed flip.
- **Touch rule** (maintenance loop, `core:304-388`): a confirmed candle whose range contains the level price is a *visit*; it is a new test only if the level was not already in contact at the previous close (`new_test = intersects and not level.in_contact`). Consecutive candles sitting on a level are one test. The first new test turns fresh into touched and emits `EVT_TAP_SUP` / `EVT_TAP_RES`.
- **Wick update:** each visit extends `wick` to the visit's extreme.
- **Invalidation:** a **close** through a fresh or touched level turns it into a flip candidate (flips on) or removes it (flips off). A confirmed flip that is closed through is removed. Normal levels have no time expiry. The only thing that ages them out is the per-role cap (3.1), which removes the oldest by `born_bar`.
- **Strength:** the indicator has **no level-strength score**. The only grading is the confluence *level quality* of the nearest same-side level (`f_context_level_quality`, `context:93-94`): confirmed flip with ≤ 1 touch = 1.0, fresh = 0.8, anything else = 0. Level **age** is not used anywhere in scoring. The website has two separate gradings: `levelQuality` for setups (`api/_lib/gseSetups.ts:164-177`: touches ≥ 2 → 0.2, flip 1.0, fresh 0.8, touched 0.5, +0.2 when a 1H/4H level sits within 0.5 ATR), and target strength 45/65/80 for plans (`websiteTargetEngine.ts`).

### 3.3 Swings, BOS and CHoCH

- **Swings:** `ph = ta.pivothigh(high, L, L)` and `pl = ta.pivotlow(low, L, L)` on confirmed candles (`core:251-264`). The last two of each give HH/LH/HL/LL (`core:266-270`).
- **Break** (`core:272-285`): a confirmed close above the latest swing high whose bar id has not been used yet. If the previous direction was ≥ 0 it is a **BOS**; if it was −1 it is a **CHoCH**. Symmetric for the low side. A break consumes that swing's bar id (`used_ph_bar`), so the same swing cannot break twice; a new swing at the same price can. Direction (`struct_dir`) is updated after both checks, so a bull and a bear break on one candle leave the direction bearish.
- **Only BOS counts as "recent structure" in the indicator.** `last_bull_bos_bar` is set by `bos_bull` only and reset by `bos_bear` or `choch_bear` (`context:116-124`). A CHoCH never satisfies BOS recency for the Golden Zone or confluence, and a CHoCH resets the opposite side. **Consequence: after a reversal the Golden Zone needs two breaks**, the CHoCH and then a BOS in the new direction. That was deliberate in v2.3 (its comment at lines 805-814 explains it), and v4.0 keeps it. The **website setups engine accepts BOS or CHoCH events** as the structure step (`gseSetups.ts:592-603`, `782-789`). Its context path (`bos_age_bars`) carries BOS only, so on the website a CHoCH counts only if its event webhook arrived.

### 3.4 Liquidity: equal highs/lows, previous day/week, sweeps

- **Equal highs/lows** (`core:442-488`): when a new wick swing high forms within `eq_atr × ATR` of a stored swing high, the higher of the two becomes a pool. Pools: ≤ 8 per side. Reference pivots: ≤ 10 per side, pruned once price trades through them (`f_prune_eq_refs`, `core:214-222`).
- **Pool sweep** (`core:490-516`): the first candle to trade through a pool consumes it. It is a sweep if that candle closes back inside. No candle direction is required.
- **Previous day/week:** `request.security("D"/"W", high[1] / low[1], lookahead_on)` (`engine.pine:8-15`), the completed previous period. Day sweep (`core:542-554`): first penetration of the day, wick through, close back inside, **and** a candle closing in the sweep's direction. Week is the same. The monthly high and low are drawn only.
- **Swing sweep** (`core:556-562`): wick through the latest swing low or high, close back inside, directional candle; consumed until a new swing forms.
- **Qualified sweep** (`core:565-569`): any of the above, with a same-side level within `sweep_snr_atr` (3.0) × ATR of the candle's extreme. **Only qualified sweeps** update the context's sweep clock (`context:106-109`), `ctx.sweep_age_bars`, Golden Zone pairing and confluence. Unqualified sweeps still produce `sweep_*` events with `qualified:false`.

### 3.5 Role reversal (flips)

`core:313-381`. A close through a level makes it a **flip candidate**: role reversed, touches 0, wick cleared, `born_bar` = now. The candidate is confirmed only by a later visit that closes on its new side with a directional candle or a rejection wick ≥ 35% of the range. Confirmation sets state 3, touches = 1, and emits `EVT_FLIP_TO_SUP/RES`. A close back through, or more than 20 bars without confirmation, removes the candidate. Candidates are excluded from nearest levels, room obstacles, confluence, live alert watch lists and the website's setup anchors.

### 3.6 Chart bias (trend score)

`core:287-292`, `f_resolve_bias` `core:227-232`. Raw swing points = HH + HL − LH − LL ∈ [−2, 2]. EMA points = +1 if close > EMA20 > EMA50, −1 if close < EMA20 < EMA50, else 0. Three cases:
- Swing points **0** (mixed or no swings): score **0**. The EMA is ignored, and so is the break fallback (`core:231` requires raw ≠ 0).
- Swing points non-zero and **against** `struct_dir`: score ±0.5 in the break's direction ("Follow Last Structure Break" on), or 0 with it off.
- Otherwise (with the break, or no break yet): swing + EMA points, clamped so the score never crosses zero.

Range −3 to +3. `bias_ok_bull` is score > 0 (`context:98`).

### 3.7 Higher-timeframe alignment

- **Indicator** (`mtf.pine`): on charts of 15m or lower, `f_bias_score` (`mtf:8`, the same rules as 3.6 with the chart's swing length) is requested for 4H, 1H and 15m. Only **closed** higher-timeframe candles are used (`mtf:51-71`: the previous candle via `[1]` with lookahead on, or the just-closed candle when both close together). `f_mtf_state` (`mtf:75-81`) is +1 or −1 only when all three agree, otherwise 0. It is a **readout only**: it does not feed chart bias, confluence, Golden Zone or alert filters (`mtf.pine` header). Sent as `ctx.mtf` and `mtf_aligned_*` events.
- **Website setups** (`gseSetups.ts:447-454`): *aligned* = full alignment, or (4H with the setup and 1H not against), or, when the snapshot has no `mtf` object, the 15m trend with the setup; *opposed* = state against, or both 4H and 1H against. Core needs aligned; A+ needs full alignment; Early only needs not opposed. These 4H/1H values come from the **15m chart's** `ctx.mtf`, not from the 4H and 1H chart instances.
- **Website plans** (`websitePlanRules.ts:423-465`): the direction is the sign of the **4H chart's own** `trend_score`; a 1H snapshot is required but only as evidence.
- **Strategy** (`strategy-helpers.pine:2-24`, `f_fresh_h4`): the H4 direction is the **last H4 break direction**, with no swing points and no EMA. It is a different quantity from the bias score.
- **So "4H direction" has two definitions in v4.0**: the bias score (indicator readout, website setups, website plans) and the last break (strategy). They can disagree, for example after a break when the swings still point the other way. Research must name which one it uses.
- **Lag:** HTF swings use the chart's Swing Lookback (10) on HTF candles. A 4H swing is confirmed 10 4H candles (about 40 trading hours) after its origin.

### 3.8 Displacement, volatility, opposing-level space

- **Displacement:** **not implemented.** No candle-size or ATR-normalised impulse measure exists in v4.0 or in the website setups engine. (`disp_bull` in `context:202` is the dashboard's *display side*, not displacement.)
- **Volatility:** ATR(14) is used only as a distance unit. There is no volatility regime filter. Volume uses **tick volume** (`volume > SMA20 × 1.2` on a directional candle, `context:171-179`); with no volume, that factor is dropped from the confirmation denominator.
- **Space (room)** (`context:80-104`): the first opposing obstacle from the close is the nearest of non-candidate opposite-role levels, active EQ pools, previous-day and previous-week high/low. Room passes when the distance is ≥ `space_mult` × ATR (2.0). **An unknown obstacle fails room** (`not na(obstacle)`). Room counts for Golden Zone and confluence; in the website it gates Core.

### 3.9 Confluence score

`context:139-201`. Per side:
`score = (structure/3 × 35 + location/3 × 30 + confirmation/den × 25 + timing × 10) / 100 × 100`
- structure = bias ok + recent BOS + swing agrees (HH or HL for bull)
- location = at level (nearest same-side level within 1 ATR) + level quality (0–1) + room
- confirmation = qualified sweep ≤ 8 bars + rejection candle ≤ 8 bars + volume spike ≤ 8 bars; den = 3, or 2 without volume. The rejection candle is a directional candle with a wick ≥ 50% of its range. It must be within 2 ATR of a same-side level, or be a sweep candle, and here **unqualified** sweeps count too (`context:161`, `cr.bull_sweep`).
- timing = 1 in London or New York (always 1 on non-intraday charts)

The score is **capped at 60** (`context:196-201`) in three cases: structure = 0; no same-side level exists; or Require Sweep is on and the required sweep is missing. With a recent BOS, "required sweep" means the BOS's latched pre-BOS pairing. Without one, it means any qualified sweep within 6 bars. A score of 75 or more, crossed upward, fires `confluence_up_*` (`alerts:195-196`). It is evidence agreement, not a probability (the indicator's own text says so).

### 3.10 Golden Zone ("Buy / Sell setup ready")

`context:149-150`:
```
long_zone = struct_dir == 1 and at_sup and bias_ok_bull and struct_ok_bull and space_ok_bull
            and (not require_sweep or bull_bos_had_sweep)
```
- `at_sup`: nearest support within 1 ATR below the close.
- `struct_ok_bull`: a bull **BOS** within 15 bars.
- `bull_bos_had_sweep`: latched **at the BOS bar**: a qualified bull sweep on that bar or within the 6 bars before it (`context:129-137`). A later sweep cannot qualify an earlier BOS.

It is evaluated on every update, including intrabar. `zone_staged_*` fires live when it turns on (`alerts:197`). It is *context*, not an entry (README).

### 3.11 Storyline

`context:205-208`, ten states: 0 conflict (swings oppose the last break, no zone), 1 / 2 Golden Zone bull / bear, 3–5 bullish near support / near resistance / open, 6–8 bearish near resistance / near support / open, 9 no break yet. Sent as `ctx.storyline.key = "context_<n>"`.

### 3.12 Sessions

`core:571-574`: by candle **open** time, in each city's local time with daylight saving: Asia 09–17 Tokyo, London 08–17, New York 08–17. Codes ASIA, LDN, NY, LDN·NY (overlap), OFF (`indicator:222`); Webhook JSON sends `LDN-NY`, and the parser stores `LDN·NY` (`websitePlanRules.ts:89-91`). The indicator gives timing points to London and New York only; website setup quality gives Asia 40% of the session weight.

### 3.13 Events and webhook contract

- **Close events** (`alerts:232-272`, realtime candle close only): `context_snapshot` (charts of 15m and higher), `bos/choch_*`, `sweep_*`, `flip_to_*`, `level_reaction_*`, `structure_changed`, `mtf_*` (the chosen chart).
- **Live events** (intrabar, `confirmed:false`, once per type per candle): `level_approach_*`, `level_tap_*` (Immediate timing), `zone_staged_*`, `confluence_up_*`, `bias_changed`, `story_changed`, `session_changed`.
- **Watch list:** level touches, approaches and `level_reaction_*` are checked against a copy of the levels taken at the previous close. That copy **excludes levels that were in contact at that close** (`alerts:16-22`, `183-187`). A reaction on the second or a later candle of one visit is therefore never reported. Levels born on this candle are watched from the next one.
- **Historical candles send nothing.** Every alert path requires `barstate.isrealtime`. Research must regenerate events from state; it cannot replay alerts.
- **Level alert budget:** level events are sent only while fewer than 8 alerts went out in the last 3 minutes (`messages:241-250`). Excess level events are skipped silently.
- **Parser** (`websitePlanRules.ts:163-343`) validates instrument, timeframe, timestamps and candle length (`bar_close_time − time` must equal the timeframe exactly, `:190`), and normalises `ctx`.

### 3.14 Website GSE setups (setup-v1), where Early / Core / A+ live

`api/_lib/gseSetups.ts`, policy `gseSetupPolicy.ts`. 15m evidence only (`setupRelevant`, `:154-160`).

- **Opening** (`:704-828`): a level event (approach, tap or reaction) for a level that has no open setup, or a confirmed candle whose level list shows a level in contact (any non-candidate state). Direction = the level's role (support → long). Skipped when the same level closed within the last 8 bars (in-contact path only), and **silently skipped when 12 setups are already open** (`:652`).
- **Checks and stages** (`:432-570`):
  - **Early** = touched **and** a qualified same-direction sweep within 8 bars **and** a reaction (the confluence rejection check, or a `level_reaction` event within 8 bars) **and** not opposed by 4H/1H. **The sweep is mandatory.**
  - **Core** = Early **and** structure (BOS or CHoCH) at or after the sweep, within 15 bars **and** close within 2 ATR of the level **and** room ≥ the required ATR **and** aligned.
  - **A+** = Core **and** full 4H·1H·15m alignment **and** level quality ≥ 0.8 **and** confluence ≥ 75 **and** London or New York.
- **Endings:** close beyond the level wick ± max(tick, 0.2 ATR) → `invalidated` (`:389-396`); an opposing break after the first stage → `structure_lost`; no touch within 8 bars, no progress within 16 bars, or 48 bars total → `expired` (`:572-589`); a policy version change → `expired`.
- **Quality** 0–100 (`:516-549`): htf 25, level 20, sweep 15, structure 15, reaction 10, room 10, session 5. Described as evidence agreement, not a probability.
- **What A+ really requires of the level.** `levelQuality` (`:164-177`) scores the anchor *as it was before this visit*: ≥ 2 touches 0.2, confirmed flip 1.0, fresh 0.8, touched 0.5, plus 0.2 if a 1H/4H level is within 0.5 ATR. A+ needs ≥ 0.8. So **only a fresh level or a confirmed flip with fewer than 2 touches can reach A+**. A touched level stays at 0.7 even with a higher-timeframe match.
- **The reaction check is not tied to the anchor.** Early accepts the indicator's confluence rejection flag (`:438-441`). That flag fires for any same-side level within 2 ATR, or for any sweep candle (section 3.9), not only the setup's own level.
- **Windows are wall-clock, not candle counts.** The engine compares times (`t − bar ≤ N × 15 min`, deadlines in ms). The indicator counts candles. The feed has a daily break (17:00–18:00 New York) and a weekend gap. A website window that spans a gap therefore covers fewer real candles than its name says, and a setup open at Friday's close expires at Sunday's first candle. Ages read from `ctx` are converted back to virtual times (`t − age × 15 min`), so across a gap they disagree with times taken from events.
- **Outcome report** (`gseSetupOutcomes.ts`): the entry is the close of the stage candle, and the result is +1R versus invalidation within the next 16 15-minute **time slots**. A candle reaching both is "ambiguous". A missing slot is a "data gap". Both are excluded from the rates, and there are no costs. Because of the daily break, **an entry after about 13:00 New York that has not resolved by 17:00 becomes a data gap and is dropped** (`:59-61`), and so are Friday-afternoon entries. That is a selection bias: slow or unresolved late-session outcomes are excluded. See B15.

### 3.15 Website trade plans and JEV (context only)

`assessWebsiteProposal` (`websitePlanRules.ts:423-509`): a confirmed 15m snapshot no older than one candle, a confirmed 4H (≤ 8h) with non-zero trend, a 1H (≤ 2h), and an untouched, not-in-contact, fresh level on the 4H-trend side within **1 ATR** of price (`maxEntryDistanceAtr = 1`, `:159`). The target engine requires ≥ 1.5R and ≤ 8 ATR (`websiteTargetEngine.ts:14-17`). Approval requires a JEV probability ≥ 0.60 (`websiteTradeTracking.ts:8`). See section 10 for what was measured.

## 4. Rejection map: every condition that can stop a candidate

### 4.1 Golden Zone (indicator, per side, every candle)

| Order | Condition | Fails when | Ref |
|---|---|---|---|
| 1 | Direction | `struct_dir` ≠ side (no break yet, or the last break was opposite) | `context:149` |
| 2 | Location | no non-candidate same-side level, or nearest > 1 ATR from close | `context:146-147` |
| 3 | Bias | trend score ≤ 0 (bull) / ≥ 0 (bear) | `context:98-99` |
| 4 | Recent BOS | no same-side **BOS** within 15 bars, or reset by an opposite BOS/CHoCH (a CHoCH alone never passes) | `context:116-127` |
| 5 | Room | first obstacle unknown, or < 2 ATR away | `context:101-104` |
| 6 | Sweep (only if Require Sweep is on) | no qualified sweep on the BOS bar or the 6 bars before it | `context:129-137`, `149-150` |

The indicator records **no rejection reason**. `ctx.confluence.<side>.checks` exposes bias, bos_recent, at_level and room booleans. The direction and sweep-pairing states are not exposed directly.

### 4.2 GSE setups (website)

Not opened: not a 15m event · no level event and no level in contact · level is a flip candidate · same level closed in the last 8 bars · **12 setups already open (silent)**.
Not Early: no touch · **no qualified sweep within 8 bars** · no reaction within 8 bars · 4H/1H opposed.
Not Core: no BOS/CHoCH at or after the sweep within 15 bars · close > 2 ATR from the level · room below required or unknown · not aligned.
Not A+: not fully aligned · level quality < 0.8 · confluence < 75 · Asia or off-hours.
Ended: invalidated · structure lost · expired · policy changed.
The engine stores per-check states (`done` / `waiting` / `failed`) and a timeline, so it can explain a stage.

### 4.3 Website trade plans

15m snapshot stale · no confirmed 4H within 8h · 4H trend 0 · no 1H within 2h · no untouched fresh level on the 4H side · nearest such level > 1 ATR away · target engine: no opposing structure / insufficient room (< 1.5R) / target beyond 8 ATR · JEV < 0.60. Rejections from the target engine are stored (`_planning.reason`); the earlier gates are not.

## 5. Repainting, look-ahead, leakage, duplicates, performance

| ID | Severity | Finding | Evidence | Research implication |
|---|---|---|---|---|
| B1 | Medium | **Live events repaint.** `zone_staged_*`, `confluence_up_*`, `bias_changed`, `story_changed`, approach and Immediate touch fire on open-candle values and can be untrue at the close. | `alerts:193-226` | Use closed-candle states only; treat live events as observations. |
| B2 | Info | Pivots are known L bars after their origin. Lines and labels are drawn back at the origin, which is visual hindsight only. | `core:251-264`, `297-300`; `indicator.pine` drawings | Make every pivot-derived fact available at the confirmation bar, never the origin bar. |
| B3 | OK | Previous D/W/M use `[1]` with `lookahead_on`, the documented non-repainting pattern. The MTF readout uses only closed higher-timeframe candles. | `engine:8-15`; `mtf:51-71` | Same rule in research: a 4H value only after its candle closes. |
| B4 | Low | `room_up/down` (JSON room) are computed only on the last bar. Webhooks are realtime, so live JSON is unaffected, but the values are not available on history. `space_ok` itself is computed every bar. | `indicator:19-20` | Recompute room from state; don't rely on the JSON field historically. |
| B5 | Medium | **Level alert budget** silently drops approach, touch and reaction events after 8 alerts in 3 minutes. The website reopens touches from in-contact levels at the close, but a dropped `level_reaction` cannot be recovered. | `messages:241-250` | Production evidence can be incomplete on busy candles; research generates every event. |
| B6 | Low-Med | The website parser rejects TradingView's **3-hour last 4H candle** (closes 17:00 New York), so that candle never produces a 4H snapshot. The website falls back to a 4H snapshot up to 8h old. | `websitePlanRules.ts:190`; DB: 4H closes only at 02/06/10/14/18 UTC | Model the same gap, or document the difference. |
| B7 | Medium | **12-open-setups cap** silently refuses new setups, with no reason recorded. | `gseSetups.ts:652` | Funnel reports must count this rejection explicitly. |
| B8 | Low | Duplicates: live events at most once per type per candle; the website deduplicates on (tf, time, event, level, phase). Tap and reaction for one level both update one setup, idempotently. | `alerts:204-210`; `websiteEvidenceKey` | One candidate per level and candle in research. |
| B9 | Medium | **Feed dependency.** Tick volume (confirmation factor) and wick extremes differ between brokers. Measured: OANDA vs BlackBull 15m closes median 0.12 apart, but a weekly high differed by 4.71. | section 10 | Research on OANDA will not reproduce BlackBull charts exactly. Report this, and test with and without volume. |
| B10 | Low | **Test harness defect.** `test-pine-subset.mjs:59` turns a function's last line into `return` even inside a loop, so the translated `f_trim_role` removes only one level per call; real Pine loops until the cap holds. | reproduced 2026-10-10 | Correct it in any parity harness. Existing tests may miss multi-level trims. |
| B11 | Info | **CHoCH asymmetry:** the indicator's BOS recency ignores CHoCH; website Core accepts CHoCH. | `context:116-124`; `gseSetups.ts:782-789` | A candidate can be Core on the website while the indicator shows no recent BOS. Record both. |
| B12 | Info | Equal-high/low sweeps need no candle direction; day, week and swing sweeps do. | `core:490-516` vs `542-562` | Treat as two sweep classes in R001. |
| B13 | Perf | Security contexts: 6 period requests plus `f_mtf_score` (2 requests) called 6 times; lower-timeframe requests only on charts of 15m or lower. Per-bar loops are O(levels ≤ 40). `max_bars_back(time, 5000)`. No algorithmic bottleneck found in core. | `engine`, `mtf`, `indicator:60` | None. |
| B14 | Info | ATR(14) warm-up and EMA warm-up: before the EMAs exist, EMA points are 0, not `na`. | Pine `na` comparison semantics | Discard a warm-up period (≥ 200 bars) in research. |
| B15 | Medium | **Outcome-report selection bias.** Website stage outcomes need 16 consecutive 15-minute time slots. Any slot inside the daily 17:00–18:00 New York break, or the weekend, ends the evaluation as `data_gap`, and data gaps are excluded from the rates. Late-NY and Friday entries are kept only if they resolve quickly. | `gseSetupOutcomes.ts:59-61`, `:116-118` | Do not compare research results with website outcome rates without correcting this. Research uses candle counts, and positions held over a gap are priced at the next open. |
| B16 | Low-Med | **Wall-clock versus candle windows.** The website's 8 / 15 / 16 / 48-"bar" windows are time spans; the indicator's 6 / 8 / 15 / 20-bar windows are candle counts. They disagree across the daily break and weekends. | `gseSetups.ts:436-446`, `578-589`; `context:110-127` | Reproducing the website needs time-based windows; reproducing the indicator needs candle counts. Record which one each result uses. |
| B17 | Low | `level_reaction_*` is reported only on the first candle of a visit (the watch list excludes levels in contact at the previous close). Later rejection candles at the same level never produce a reaction event. | `alerts:16-22`, `184-187` | The website's Early "reaction" can still pass through the confluence rejection flag. Research should record both sources separately. |
| B18 | Info | **Two definitions of "4H direction".** Bias score (indicator readout, website) versus last H4 break (strategy). | `mtf:8-44`; `strategy-helpers.pine:5-24` | State which one an experiment stratifies by. |

### 5.1 Porting hazards (Pine → Python)

These are not defects in GSE. They are places where a straightforward port would silently differ from TradingView.

| ID | Hazard | Evidence | Required handling |
|---|---|---|---|
| P1 | **Pivot tie rule unknown.** `ta.pivothigh` / `ta.pivotlow` decide what happens when neighbouring values are equal. That rule is internal to TradingView, and no repository test emulates it. Gold M15 bodies often share a price (0.01 ticks), so the tie rule changes which levels and swings exist. | `core:251-252`, `299-300`; no `pivothigh` in any `test-*.mjs` | Determine the rule empirically, by parity against stored TradingView snapshots, **before** any experiment. Keep both candidate rules behind a switch until then. |
| P2 | **Short-circuit side effects.** `valid0 and not f_merge_into(...)`: `f_merge_into` mutates a level (fresh → touched). Pine v6 evaluates `and` lazily, so it runs only for valid pivots. | `core:392`, `399` | Keep the evaluation order: no merge side effect for an invalid pivot. |
| P3 | **Order of operations** (section 1.1). For example, breaks use the swing confirmed on the same candle, and level maintenance runs before new pivots are added. | `core:255-285`, `304-403` | Port function by function in the same order; test with the repo's translated Pine functions. |
| P4 | **Session-anchored higher timeframes.** TradingView's D, W and 4H candles for this symbol start at 18:00 New York. The last 4H candle of each day is 3 hours long, and there is a daily 1-hour break. | `gse_lab/data.py` docstring; B6 | Build HTF candles with the same anchors (the drafted `aggregate()` does). Test them against stored close times. |
| P5 | **HTF value timing.** A 4H or 1H value is usable only from the 15m candle on which that HTF candle closes. | `mtf:51-65` | Join HTF values on `close_time` (as-of, backward). Never join on open time. |
| P6 | **`bar_index` arithmetic.** Ages, recency and candidate expiry count candles, including across weekends. | `context:110-127`; `core:317` | Index by candle position, not by time. |

## 6. Gaps between the brief and what GSE defines

- **No objective entry, stop, target or exit in the indicator.** Any backtest of indicator setups needs an explicitly labelled **research execution model**. Existing models: the Pine strategy (fresh touch + H4 + website targets), the website setups outcome (+1R vs invalidation, 16 candles, no costs) and the website plan engine.
- **No displacement measure, no level-age effect, no volatility regime.** Testing R008 means adding a new definition, which would be a research rule, not baseline.
- **No calibrated probability anywhere.** The confluence score and setup quality are additive evidence points. JEV probabilities were measured to be uninformative (section 10).
- **No rejection log in the indicator.** Section 4.1 has to be reconstructed in research.

## 7. Existing research assets

- `tradingview/gse_4.0/BACKTEST.md`: a chronological protocol (train 2023–24, validate 2025, test 2026), a normalised trade CSV and one-at-a-time sensitivity lists. Not executed.
- `tradingview/gse_4.0/research/study.py`: post-processes TradingView Strategy Tester exports. It is not a backtester.
- `GoldStructureEngineStrategy_4.0.pine` with 551 + 1,735 logic comparisons against the website target engine (`FRESH_LEVEL_STRATEGY.md`). Not compiled in TradingView by these tests.
- `gse-website/scripts/replay-gse-setups.mts`: replays stored production evidence through the real setups engine (read-only).
- Stored production evidence: `gse_website_evidence` (BlackBull feed, 15m/1H/4H snapshots and events since 2026-09-29). This is the only source of real TradingView outputs available for parity checks.
- `gse-research/gse_lab/` (this repository, uncommitted draft): an OANDA M15 downloader (mid OHLC, bid/ask close, tick volume, to Parquet), TradingView-style 1H/4H/D/W aggregation, and a per-year quality report. **It has not been run here.** There is no `data/` directory and no tests (`tests/` is empty). Two limitations: the `spread` column is measured at the candle close only, and the weekly `close_time` is inferred from the last candle present.

## 8. GSE v2.3 (reference)

`tradingview/gse_2.3/GoldStructureEngine_2.3.pine` (1,410 lines). `GSE_2.3_Single_Timeframe_Review.md` reviewed an earlier 1,249-line revision, so its line numbers and some findings may not match the current file. The differences that matter for research:
- **Setups lived in Pine:** `setup_bull = bos_bull and bias_ok_bull and space_ok_bull and (not i_require_sweep or sweep_ok_bull)` (lines 815-816). A qualifying sweep upgrades **CORE** to **A+** ("4/4 Confluence"); "Require Liquidity Sweep for Setup" is off by default. The candidate is the **BOS candle itself**, not a retest.
- Single timeframe (no MTF); clustering **on** by default; a reference trade plan with stop and target inside the indicator.
- Its own review lists unresolved issues: `long_zone/short_zone` accept any three of four conditions and do not require `at_sup/at_res` or enforce the sweep switch; the trade-plan readiness differs from its message.
- In v2.3, research question R001 is literally **"CORE versus A+"**.

## 9. Disagreements between documents and code

- `AUDIT.md` (2026-09-29) describes a rebuild that added frozen reference plans and removed directional MTF requests. **Current code has no plans** (removed 2026-10-05, `CHANGELOG.md`) and **has MTF requests again** (`mtf.pine`, readout only). Its F1–F3 fixes are present in current code.
- `README.md` (4.0) describes JEV approval at 60% as the trade-proposal path. That matches the code, but see section 10 for its measured value.
- `BACKTEST.md` describes "Select Entry Model = BOS" as the baseline protocol, with sweep-required variants, BOS reference plans and 30-bar holding. `FRESH_LEVEL_STRATEGY.md` and the code say those modes were archived (`audit/strategy-before-simplification/`). The current strategy is fresh touch + H4 only. `BACKTEST.md`'s chronological split (train 2023–24, validate 2025, test 2026-01-01 to 2026-09-29) was declared for that archived strategy.

## 10. Measured facts available before research (2026-10-10)

**Provenance: not re-verified.** These come from read-only checks in the first session on 2026-10-10: database queries, OANDA API pulls and a TypeScript prototype that was later deleted at the owner's request. The second pass could not reproduce them from the repository, because there is no local data and the prototype is gone. Treat them as leads. The research engine has to reproduce them before they are relied on.

**Data exposure.** The prototype replay below looked at website Early-stage outcomes on OANDA data for **2023–2025**. That is a different candidate definition from R001's, but the same period and a sweep-related rule (Early makes the sweep mandatory). Any period chosen as an "untouched" test set must take this into account (see `R001_PLAN.md`).
- **Feed:** OANDA XAU_USD M15 (practice API) has every 15m, 1H and 4H BlackBull snapshot close time. Prices differ by a median of 0.12; weekly extremes differ by up to 4.71. OANDA history starts 2006-03-19. Early years have single-tick candles and spreads of 2.5–10; the median spread in 2026 is about 0.70 (≈ 10% of a 15m ATR).
- **Production setups** (`replay-gse-setups.mts --days=14`): 47 setups, 2 Early, 0 Core, 0 A+.
- **Prototype replay** (TypeScript port, since deleted at the owner's request, OANDA 2023–2025): about 8.2k setups, about 2 Early per week, 7 Core in three years, 0 A+. Early entries at 1R / 16 candles with spread averaged −0.24R (2023–24) and −0.44R (2025). The same prototype matched stored TradingView snapshots 100% on structure, swing, trend, 4H/1H alignment, Golden Zone, BOS/sweep ages and nearby equal highs/lows. Its level lifecycle was identical to the translated Pine code on 89,274 candles.
- **Trade plans:** none created since 2026-09-30. In the replay, the nearest untouched fresh level on the 4H side was at least 1.9 ATR away (median 14.8), against the 1 ATR gate.
- **JEV:** 887 reviews scored 0.20–0.51 whatever the reward:risk, with a correlation of 0.06 to real outcomes. A near-certain trade scored 0.41.

## Appendix A. Second-pass changes to the first draft (2026-10-10)

Corrections (the first draft was wrong or imprecise):
- **Baseline version.** The first draft reported a version conflict in the brief (v4.0 versus v2.3). The current brief says v4.0 for both the audit and the reproduction, so the conflict is gone.
- **Bias with mixed swings (3.6).** With swing points = 0, the score is always 0. The first draft said ±0.5. The break fallback applies only when non-zero swings oppose the break (`core:231`).
- **Strategy fingerprint (0).** The first draft's abbreviated SHA-256 for the strategy had the wrong suffix. Full hashes are now listed.
- **Confluence cap (3.9).** Without a recent BOS, the Require Sweep cap uses "any qualified sweep within 6 bars", not the BOS pairing (`context:196-197`).

Additions (correct in the first draft, but missing):
- Order of operations per candle (1.1) and Pine → Python porting hazards P1–P6 (5.1). P1 (pivot tie rule) is the main one: no repository test covers it. The first session's prototype reportedly matched stored snapshots on structure, so a rule that works existed, but it was not recorded.
- After a reversal the Golden Zone needs a CHoCH and then a BOS (3.3).
- Two definitions of "4H direction" (3.7, B18). The website setups read HTF values from the 15m chart's `ctx.mtf`.
- A+ can only be reached from a fresh level or a confirmed flip with fewer than 2 touches (3.14).
- The rejection check counts unqualified sweeps, and Early's reaction is not tied to the anchor level (3.9, 3.14).
- Website windows are wall-clock (B16). The outcome report drops late-session and Friday entries as data gaps (B15).
- `level_reaction` covers only the first candle of a visit (B17). Historical candles send no alerts (3.13).
- Status of the drafted `gse_lab` pipeline (7), the stale `BACKTEST.md` (9), and provenance and data-exposure notes for section 10.
