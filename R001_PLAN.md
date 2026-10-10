# R001: Does requiring a liquidity sweep improve 15m XAU/USD setups?

Status: **proposed, not started.** It depends on `GSE_BASELINE_AUDIT.md` (verified 2026-10-10) and on the owner decisions at the end of this file. Revised 2026-10-10 after the audit's second pass.

## Question

Within GSE v4.0 on 15m gold, does requiring a qualified pre-BOS liquidity sweep improve risk-adjusted outcomes after costs? Does the answer change with 1H and 4H context?

## Why the Golden Zone is the candidate (smallest test)

GSE v4.0 has three different "setups" (audit section 4). The **Golden Zone** is the smallest valid unit:
- Its sweep requirement is **an existing input**, *Require Sweep for Golden Zone* (`context:149-150`). The variant changes exactly one baseline switch and invents no rule.
- It is computed entirely by the indicator's core and context. No website code needs to be ported.
- 1H/4H context comes from the indicator's own readout (`f_bias_score` on closed candles, `mtf.pine`). R001 can stratify by it without adding a filter.

The brief lists four sweep treatments. This plan tests the first two directly (mandatory versus optional) and the fourth descriptively (strata). The rest are separate follow-ups:
- **R001b**: the website GSE setups, where the sweep is mandatory for Early. This needs the setups engine ported.
- **R001c**: the sweep as a scoring factor. The confluence score already contains it.
- **A context-dependent sweep rule.** It is proposed only if the strata here point to one.

## Design

| Item | Definition |
|---|---|
| Candidate | A 15m candle whose **close** turns the Golden Zone on for a side: off at the previous close, on at this close. Intrabar staging is not used (audit B1). |
| Control (C0) | GSE v4.0 defaults: Require Sweep = **off**. |
| Variant (V1) | Require Sweep = **on**. This is the only change. Everything else stays at defaults. |
| What V1 does to the candidates | V1's candidates are **K ∪ E**. **K**: C0 candidates whose BOS had a paired sweep (`bos_had_sweep` true on the candidate candle). **R**: C0 candidates without one, which V1 removes. **E**: V1-only candidates, where a new swept BOS turns the zone on while C0's zone was already on. V1 is therefore *not* a pure subset of C0, and E is reported separately. |
| HTF strata (recorded, not filters) | From the indicator's 4H and 1H **bias scores** on closed candles at the candidate (audit 3.7). **Aligned**: both with the side. **Partial**: one with, the other 0. **Neutral**: both 0. **Opposed**: at least one against. A secondary breakdown uses the 4H **last-break direction**, the strategy's definition (audit B18). |
| Sweep class (recorded) | The paired sweep's source: swing, equal H/L, previous day, previous week (audit B12). |
| Comparison | V1 versus C0 overall, per stratum and per period, decomposed into "remove R" and "add E". Also K versus R inside C0, the rejection-funnel view the brief asks for. |

### Research execution model RXM-1 (labelled; not GSE behaviour)

GSE defines no entry or exit (audit section 6). R001 therefore uses one fixed, documented model for both arms:
- **Entry:** the next candle's open after the signal close. Longs buy at the ask; shorts sell at the bid. This needs bid/ask OHLC (stage 2).
- **Stop:** the anchoring level's wick ± max(tick, 0.20 × ATR), rounded outward. This is the website's invalidation and stop buffer. The anchoring level is the nearest same-side level that satisfied `at_sup` / `at_res`. Longs are stopped on the bid, shorts on the ask.
- **Target:** the first opposing obstacle (the one that made room pass) minus max(tick, 0.10 × ATR), the website's target clearance.
- **Gap at entry:** if the entry open is already beyond the stop or the target, the trade exits at that open, and this is flagged.
- **Time limit:** 16 **candles**, not wall-clock time, then exit at the close. A position held over the daily break or a weekend is priced at the next open.
- **Same-candle stop and target:** counted as a stop. A sensitivity run resolves those candles with OANDA M1 data.
- **Overlap:** each candidate is scored independently. A second report keeps at most one open trade per side.
- **Costs:** bid/ask spread on every fill, plus adverse slippage on entries and stops at 0, 0.10 and 0.30 price units.

## Data and periods

OANDA XAU_USD M15 mid and bid/ask OHLC, with 1H/4H/D/W built using TradingView's session anchors (audit P4). The usable start year comes from the per-year quality report. Proposed chronological split, to confirm after that report:
- **Train:** first usable year to 2018. Rules are frozen; R001 itself tunes nothing.
- **Validate:** 2019–2022. The decision rule below is applied here.
- **Test:** 2023-01-01 to the last complete week, opened **once**, after the owner approves the validation conclusion. It is reported in two parts:
  - **2023–2025, "exposed":** the first session viewed website Early outcomes, a related sweep-mandatory rule, on this period (audit section 10).
  - **2026-01-01 onward, "unexposed".**

If the quality report rejects early years, the split shifts, keeping 2023 onward as the test.

This split differs from `BACKTEST.md` (train 2023–24 / validate 2025 / test 2026), which was declared for the archived BOS strategy (audit section 9). Two reasons: OANDA history allows a much longer train/validation span, and 2023–2025 is already partly exposed.

## Metrics (per arm, per stratum, per period)

- Trades, trades per week and per month, and the R / E counts.
- Win rate; average win R and average loss R.
- **Expectancy in R after costs**; profit factor; maximum drawdown in R.
- MAE / MFE.
- Results by session (Asia, London, London–New York overlap, New York, off) and by direction.
- Sensitivity to slippage and to the same-candle rule.

**Uncertainty:** a 90% interval for the expectancy difference V1 − C0, from a **paired block bootstrap by calendar week**. Candidates cluster, and the two arms share K. A stratum with fewer than 100 trades in either arm is reported as **inconclusive** and not used for the decision.

## Decision rule (fixed before running)

Recommend requiring the sweep only if, on the **validation** period:
1. the expectancy difference V1 − C0 is positive and its 90% interval excludes 0,
2. the maximum drawdown in R is not worse, and
3. the direction of the effect holds in every stratum with enough trades.

Otherwise the recommendation is to **keep the current rule** (sweep optional). If the effect exists only in some strata, for example only when 4H/1H are not aligned, it is reported as a candidate context-dependent rule for a separate future experiment, not as a result of R001.

## Implementation stages (smallest path)

Each stage ends with tests run, a leakage check, saved results, and a short report of the files changed and the commands used.

0. **Initial commit** of `gse-research` (audit, plan, draft). Every result has to record a git commit, and the repository has none yet.
1. **Layout:** rename the draft package `gse_lab` to `gse_research`, and add `config/`, `results/` and `tests/` as in the brief.
2. **Data:** extend the downloader to keep bid and ask OHLC, then download (the OANDA practice token is already in `.env`). Write Parquet and run the per-year quality report. Tests:
   - no duplicate candles, and monotonic time;
   - the 3-hour last 4H candle, the daily 17:00–18:00 New York break, and DST weeks;
   - 1H/4H close times equal to the stored BlackBull snapshot close times.
3. **`structure.py`:** a port of `core.pine`, `context.pine` and `f_bias_score`, keeping the audit's order of operations (1.1) and porting hazards P2–P6. On every candle, record **every** failing Golden Zone condition and the first one, in audit 4.1 order.
4. **Parity gate, before any experiment:**
   - Settle the pivot tie rule (audit P1) against stored TradingView snapshots.
   - Check that the level lifecycle is identical to the real Pine functions, translated by the repo's harness with defect B10 corrected, on identical candles.
   - Check structure, swing, trend score, HTF readout, Golden Zone, BOS/sweep ages and nearby equal H/L against the stored snapshots. Feed-sensitive fields (tick volume, extremes) are reported, not asserted.
5. **Anti-look-ahead tests:**
   - Truncation invariance: everything up to candle *t* is unchanged when later candles are removed.
   - A higher-timeframe value is used only from the candle on which its HTF candle closes.
   - A pivot is used only from its confirmation candle.
6. **`signals.py`, `backtest.py` (RXM-1), `metrics.py`, `experiments.py`:** versioned R001 config files for C0 and V1 in `config/`. Each result records the config hash, the dataset hash and the git commit.
7. **Run R001** on train and validation, then write `results/R001/report.md`, the trade logs and the rejection funnel. **Stop and ask** before opening the test period.

## Out of scope for R001

- Website GSE setups (R001b) and the sweep as a scoring factor (R001c).
- Parameter optimisation, and the other experiments R002–R010.
- Any change to the indicator, the strategy or the website.

## Decisions needed from the owner

Defaults are in bold. Work will proceed on the defaults unless the owner objects.

1. **Candidate:** **the Golden Zone** (smallest), or the website GSE setups' Early stage first (needs the setups engine ported).
2. **Research feed:** **OANDA** (programmatic history from 2006, measured close to BlackBull), or BlackBull, the live feed, which has no bulk history available here. With OANDA, results will not match BlackBull charts exactly (audit B9).
3. **Parity data:** **read-only access** to `gse_website_evidence` for the stage 4 parity gate, or an export of the 15m/1H/4H snapshots since 2026-09-29.
4. **Split:** the **split above**, with the exposed / unexposed test reporting.
5. **Stage 0 commit:** **yes**, as an initial commit on `main` in `gse-research`.
