# Models A and B: mapping from GSE v4.0

Date: 2026-10-10 · First deliverable of the two-model specification · Read-only: no Pine or website source was changed.

This maps every step of the two specified models to what **GSE v4.0 actually does**, as verified in `GSE_BASELINE_AUDIT.md`. Each step is marked:

| Mark | Meaning |
|---|---|
| **EXISTS** | v4.0 implements the step as specified; port it as is |
| **PARTIAL** | a related v4.0 rule exists but does not cover the step; the gap is named |
| **MISSING** | v4.0 has no rule for it |
| **DECISION** | cannot be implemented until a definition is chosen (section 5, D-numbers) |

Sources: `gse-website` at commit `19564ee`. References follow the audit's convention: `core:313` is `tradingview/gse_4.0/src/core.pine` line 313, and the same for the other `src` parts. Website paths are relative to `gse-website/api/_lib/`. "Audit 3.14" means section 3.14 of `GSE_BASELINE_AUDIT.md`.

## 1. Where v4.0 already comes close

GSE v4.0 has no "Model A" or "Model B", but two existing parts come close. They are the starting point for both models:
- **Website GSE setups (`setup-v1`, `gseSetups.ts`)** already run most of Model A's sequence on 15M levels: touch → qualified sweep → reaction → BOS/CHoCH → location, room and 4H/1H alignment → Early / Core / A+ (audit 3.14). They have no Daily context and no pullback definition, and the sweep is mandatory.
- **The core flip lifecycle (`core:313-381`)** already runs most of Model B's sequence: a close through a level → flip candidate → retest with rejection → confirmed flip (audit 3.5). Nothing turns a flip retest into a trade candidate.

The Pine strategy adds one more reusable rule: its **selection of the nearest fresh level on the 4H-trend side** (`strategy-helpers.pine:26-34`).

## 2. Shared context

| Spec | v4.0 today | Mark |
|---|---|---|
| Daily: macro direction | **MISSING.** Daily data is used only for previous-day high/low liquidity references (`engine:8-9`, audit 3.4), never for direction. | MISSING · DECISION D2 |
| 4H: primary trend | **PARTIAL, with two definitions.** The indicator's 4H bias readout (`f_bias_score` on closed 4H candles, `mtf:8-44`, `51-67`) feeds the website setups' alignment. The website plans use the 4H chart's own `trend_score` sign. The strategy uses the **last 4H break** direction instead (`strategy-helpers.pine:5-24`). See audit 3.7 and B18. | PARTIAL · DECISION D3, D4 |
| 1H: thesis confirmation | **PARTIAL.** The 1H bias readout (`mtf.pine`). The website setups count it as "aligned" when 4H agrees and 1H is not against, and "opposed" when both are against (`gseSetups.ts:447-454`). The website plans require a 1H snapshot as evidence only. | PARTIAL · DECISION D9 |
| 15M: level interaction and trigger | **EXISTS:** levels, touches, flips, sweeps and BOS/CHoCH on the 15M chart (`core.pine`, `context.pine`). | EXISTS |
| Confirmed, time-aligned data | **EXISTS.** State changes only on confirmed candles (`engine:17`). Previous-period references use `[1]` with lookahead on, and HTF values come from closed candles only (audit B3). `gse_research.data.align` reproduces both timings and is tested for look-ahead. | EXISTS |

## 3. Step-by-step mapping

### Model A: countertrend reversal

**Trade direction is the first decision (D1).** Steps 2–3 describe a 15M pullback *against* the dominant trend and a fresh level *in its path*. The natural reading (A1) is that the trade reverses the 15M pullback, i.e. it goes **with** the Daily/4H trend. "Countertrend" then describes the 15M leg being traded out of. v4.0 already behaves this way: website setups take a support touch long only when 4H/1H are not opposed. The strategy buys fresh support only when the 4H direction is up. The other reading (A2) is a trade **against** the dominant trend. It is a different hypothesis and would be tested separately if wanted.

| # | Spec step | v4.0 today | Mark | Gap / decision |
|---|---|---|---|---|
| A1 | Dominant Daily/4H trend | 4H readout only; no Daily (section 2). | PARTIAL | D2, D3, D4 |
| A2 | 15M pullback against that trend | No pullback concept. Storyline state 3 ("bullish structure near support", `context:205`) uses the 15M chart's own structure, not the higher timeframes. Website setups open on any touched level, pullback or not (`gseSetups.ts:704-828`). | MISSING | D5: what counts as a pullback, and when it starts and ends |
| A3 | Fresh 15M SNR level in the pullback path | **Fresh levels EXIST** (audit 3.1–3.2). A level is fresh until its first new visit. A pivot touched during its confirmation bars starts as touched. **Selection EXISTS in the strategy:** the nearest level that is fresh, untouched and not in contact, on the 4H-trend side (`strategy-helpers.pine:26-34`). The website plans use the same rule, but only within 1 ATR of price (`websitePlanRules.ts:423-509`). | EXISTS · DECISION | D6: whether to cap the distance, and whether the level must predate the pullback |
| A4 | Level interaction; record whether a sweep occurred | **Touch EXISTS:** a confirmed candle reaching the level starts a new visit (`core:357-363`, `375-381`). The website records it as `touched_at`. **Sweeps EXIST as GSE defines them:** swing, equal H/L or previous day/week liquidity taken and closed back, counted as *qualified* when a same-side level is within 3 ATR (`core:490-569`, audit 3.4). The website's Early stage needs a qualified sweep within 8 bars (`gseSetups.ts:436-437`, `506`). **A sweep *of the SNR level itself* does not exist:** a wick through support that closes back above is a touch. | PARTIAL | D7: which visit counts. D8: which sweep definition to record, and in which window. Mandatory versus optional is an experiment arm, as the spec requires; setup-v1 makes it mandatory. |
| A5 | 1H structural context | 1H bias readout and the website's aligned / opposed rules (section 2). | PARTIAL | D9 |
| A6 | Objective 15M reversal trigger | Candidate rules EXIST. The website's Early "reaction" is either (a) the indicator's rejection flag: a directional candle with a wick ≥ 50% of its range, within 8 bars, near *any* same-side level within 2 ATR or on any sweep candle (`context:157-166`); or (b) a `level_reaction` event for the touched level: closed back, directional, wick ≥ 50% (`alerts:69-76`), reported only on the first candle of a visit (audit B17). Core adds a BOS **or CHoCH** after the sweep within 15 bars (`gseSetups.ts:442-446`). The Golden Zone accepts BOS only; after a pullback that flipped 15M structure, the first break back with the trend is a CHoCH (audit 3.3). | PARTIAL | D10: trigger definition (tied to the touched level or not) and its window |
| A7 | Candidate only when the configured conditions are met | Website stages are a fixed, versioned policy: Early = touch + sweep + reaction + not opposed; Core adds structure, location ≤ 2 ATR, room and alignment; A+ adds full alignment, level quality ≥ 0.8, confluence ≥ 75 and London/New York (`gseSetups.ts:501-514`). | PARTIAL | Configuration: which steps are mandatory in each experiment arm |
| A8 | Invalidation, entry assumptions, target method | **Invalidation EXISTS and is consistent across v4.0:** the level's wick ± max(tick, 0.2 ATR), rounded outward (`gseSetups.ts:181-195`; the same buffer in the strategy and the plans). **Entry:** the website uses the stage candle's close; the strategy uses a resting limit at the level. **Target:** the website target engine picks TP2, the best-ranked structure ≥ 1.5R and ≤ 8 ATR away (`websiteTargetEngine.ts:13-19`, used by the strategy and the plans); the setups' outcome report uses +1R instead. **Exit:** no time limit in the strategy; 16 slots in the outcome report, which is biased by the daily break (audit B15). The indicator itself has none of these (audit 6). | PARTIAL | D14 entry, D15 stop, D16 target and exit |

### Model B: trend continuation through role reversal

| # | Spec step | v4.0 today | Mark | Gap / decision |
|---|---|---|---|---|
| B1 | Dominant Daily/4H trend | 4H readout only; no Daily (section 2). | PARTIAL | D2, D3, D4 |
| B2 | A 15M SNR level | Body-pivot levels with the fresh / touched / candidate / flip states (audit 3.1–3.2). | EXISTS | — |
| B3 | Confirmed break in the dominant direction | A **close** through a fresh or touched level makes it a flip candidate. A confirmed flip that is closed through is removed, so a level never flips twice (`core:346-356`, `364-374`). There is no break-quality measure (distance, displacement) and no direction filter. BOS is a separate concept: a close beyond a *swing*, not a level. | PARTIAL | D11: break definition, eligible level states, direction filter |
| B4 | Track the role transition (S→R or R→S) | **EXISTS:** the candidate takes the new role, touches restart at 0 and `born_bar` restarts, so the per-side cap keeps it as the newest level. It expires after 20 bars, and a close back through removes it (`core:313-321`, `332-334`). Candidates are excluded from nearest levels, room, confluence, alerts and the website (audit 3.5). | EXISTS | — |
| B5 | Retest of the flipped level | **EXISTS, merged with confirmation.** The flip is confirmed *by* a retest: a later candle reaches the level, closes on its new side, and is directional or has a rejection wick ≥ 35% of its range (`core:322-331`, `335-343`). That sets touches to 1 and sends `flip_to_support` / `flip_to_resistance` (`alerts:253-256`). It can happen on the candle right after the break. A near miss (price turns a few ticks short) never counts. Later visits to a confirmed flip only add touches. | EXISTS · DECISION | D12: enter on the confirming retest or a later one; minimum bars after the break; touch tolerance |
| B6 | 1H confirmation and 15M continuation structure | 1H: the readout (section 2). 15M: `struct_dir`, HH/HL swings and BOS recency latched to the current regime (`core:266-285`, `context:116-127`). | PARTIAL | D9 (1H), D13 (15M continuation rule) |
| B7 | Candidate only when the configured conditions are met | No rule turns a flip retest into a candidate. A confirmed flip gets the top level quality: 1.0 in confluence while it has ≤ 1 touch (`context:93-94`), and 1.0 in the website setups (`gseSetups.ts:164-177`). Website setups do open on touches of flipped levels, but then follow the Model A stages, sweep included. The Golden Zone can coincide with a flip retest, but it does not require one. | PARTIAL | Configuration |
| B8 | Invalidation, entry assumptions, target method | As A8. | PARTIAL | D14, D15, D16 |

### Research requirements

| Requirement | Status |
|---|---|
| Keep the models separate in code, logs and reports | To build: `signals/model_a.py` and `signals/model_b.py` over the shared structure port, with separate configs, trade logs and reports |
| Audit the source before implementing its rules | Done for v4.0: `GSE_BASELINE_AUDIT.md`, plus this mapping |
| Ambiguous definitions as configurable hypotheses | Every D-number in section 5 becomes a config key with a named default; no default is presented as a GSE rule |
| Compare mandatory versus optional 1H confirmation and sweeps | Two switches per model: `require_1h` and `require_sweep`. One change per experiment, as in R001. |
| Log every rejected candidate and its reason | v4.0's indicator records none (audit 4.1); the website keeps per-check states. To build: a per-model funnel recording the first failing step and all failing steps |
| Frequency, expectancy, PF, drawdown, MAE/MFE, out-of-sample stability | Planned `metrics.py`, on the R001 split (train 2016–18, validate 2019–22, test 2023+) |
| Spread, slippage, execution | Data has bid/ask OHLC (Stage 2). Execution follows D14–D16, with the same cost model as R001. |
| Never change the live Pine Script | Respected: research is Python only. |

## 4. v4.0 behaviours both models depend on

These come from the audit. Each one changes candidate counts or outcomes, so the port must reproduce it exactly.

| Behaviour | Audit | Effect on A / B |
|---|---|---|
| Two definitions of 4H direction: bias score (readout, website) versus last break (strategy) | 3.7, B18 | D3 must pick one |
| The Golden Zone and BOS recency ignore a CHoCH; the website accepts it, but only through its event | 3.3, B11 | A6 trigger, B6 continuation |
| `level_reaction` is reported only on the first candle of a visit | B17 | A6 if the trigger is tied to the level |
| The website's confluence rejection flag is not tied to the touched level | 3.14 | A6 |
| Sweep qualification needs a same-side level within 3 ATR; there is no "sweep of the level itself" | 3.4 | A4, D8 |
| Room fails when the first obstacle is unknown | 3.8 | Room checks and targets |
| Merging is off: only exact-tick duplicates merge, so pivots a few ticks apart are separate levels | 3.1 | A3 "nearest fresh level" can pick one of two near-identical levels |
| A+ is reachable only from a fresh level or a confirmed flip with < 2 touches | 3.14 | A7 if A+ is used as a filter |
| Website windows are wall-clock; the indicator counts candles | B16 | Research counts candles and records which convention each rule uses |
| The website outcome report drops late-session and Friday entries | B15 | Do not compare with website outcome rates |
| The pivot tie rule is unknown and untested | P1 | All levels and swings; settled at the Stage 4 parity gate |

## 5. Decisions required before implementation

Each is a research hypothesis, not a GSE rule. The proposed default is what would be implemented first. It is labelled as such in configs and reports, and alternatives stay switchable.

| ID | Question | Options | Proposed default |
|---|---|---|---|
| D1 | Model A trade direction | A1 with the Daily/4H trend (reverse the 15M pullback) · A2 against it | A1, which is v4.0's own behaviour; A2 only as a separate model if wanted |
| D2 | Daily context | Bias score (`f_bias_score`) on closed D candles · D last-break direction · none | Bias score on closed D candles, recorded as a stratum before it is used as a filter |
| D3 | 4H trend | Bias score on closed 4H candles (indicator readout, website) · last 4H break (strategy) · both agree | Bias score; the last break recorded |
| D4 | Combining Daily and 4H | 4H decides and Daily must not oppose · both must agree · 4H only | 4H decides, Daily must not oppose; "both agree" as an arm |
| D5 | Model A: 15M pullback | 15M `struct_dir` against the trend (a 15M break against it has printed) · retracement ≥ k × ATR from the last with-trend 15M swing extreme · counter-swings (LH/LL in an uptrend) | 15M `struct_dir` against the trend; the k × ATR retracement as an alternative arm |
| D6 | Model A: level "in the path" | Strategy rule (nearest fresh, untouched, not-in-contact level on the trend side) · plus a maximum distance (the plans use 1 ATR) · plus the level formed before the pullback began | Strategy rule; distance cap as a parameter |
| D7 | Model A: which interaction | First visit of the fresh level only · any visit | First visit (the level stops being fresh on it) |
| D8 | Model A: "a sweep occurred" | GSE qualified sweep within N bars before or at the touch (website: 8) · wick through the level by ≥ x ATR and close back · both, recorded separately | Record both; the GSE qualified sweep within 8 bars is the one the mandatory arm uses |
| D9 | 1H context (A5, B6) | 1H bias not against the trade (website "aligned") · 1H bias with the trade · a 1H break in direction within N 1H candles | 1H bias not against the trade; mandatory versus optional as experiment arms |
| D10 | Model A trigger | Website reaction rule (rejection flag or `level_reaction`) · rejection candle at the touched level only · 15M CHoCH · 15M BOS; window N bars after the touch | Rejection candle at the touched level within 8 bars; the website's untied rule and CHoCH as alternative arms |
| D11 | Model B break | One close through the level (v4.0) · close by ≥ x ATR · two closes · coincident BOS; eligible states: fresh only · fresh or touched | One close (v4.0), in the dominant direction, fresh or touched level; break distance recorded |
| D12 | Model B retest | Enter on the confirming retest (v4.0 flip confirmation) · on a later visit of the confirmed flip; minimum bars from the break; touch tolerance | The confirming retest; minimum bars and tolerance recorded, not filtered |
| D13 | Model B 15M continuation structure | 15M `struct_dir` with the trade at the retest · a BOS with the trade after the retest | `struct_dir` with the trade at the retest |
| D14 | Entry assumption | Next candle's open after the trigger close · resting limit at the level (strategy) · trigger close (website) | Next open, as in R001's RXM-1; the limit at the level as a sensitivity run |
| D15 | Stop | Level wick ± max(tick, 0.2 ATR), rounded outward (website setups, plans, strategy) | That rule, v4.0's own, anchored to the traded level |
| D16 | Target and exit | Website target engine TP2 (≥ 1.5R, ≤ 8 ATR) · first opposing obstacle (R001's RXM-1) · time limit or none | Target engine TP2 (v4.0's own rule; no candidate when there is no valid target, logged as a rejection). First obstacle and a 16-candle time limit as sensitivity runs. |

## 6. Proposed order

1. **Decide D1** (owner). It changes what Model A is. The rest can start on their defaults.
2. **Shared building blocks:** the planned Stage 3 port of `core.pine`, `context.pine` and `f_bias_score`. The bias engine runs on 15M, 1H, 4H and D candles, and HTF values are joined with `data.align` (no look-ahead). R001 needs the same port, so nothing is built twice.
3. **Model B first.** Its full sequence (break → candidate → retest → confirmed flip) is in `core.pine`, which the port covers. It needs three new definitions (D11–D13). Model A needs four (D5, D6, D8, D10), plus parts of the website setups engine.
4. **Model A**, then the mandatory-versus-optional comparisons for 1H and sweeps, one change per experiment.
