Gold Structure Engine — Engineering Research & Backtesting Plan

Project: GSE Engineering Research
Owner: Gold Structure Engine
Primary instrument: XAU/USD
Current baseline: GSE v4.0
Objective: Build a reproducible research and backtesting engine to discover which market-structure rules improve the quality, frequency and risk-adjusted performance of GSE setups.

1. Your role

Act as a senior quantitative developer, Python engineer, trading-system researcher and Pine Script specialist.

Your job is to investigate the existing GSE code, understand its actual rules, build an independent research engine, test each hypothesis scientifically, and recommend improvements supported by measurable evidence.

Do not assume that more filters create better trades. Do not invent strategy rules or silently change existing behaviour.

2. Phase 1 — Audit the existing GSE

Before writing or changing code:

1. Locate and read the complete GSE v4.0 Pine Script source.
2. Document the current architecture, inputs, calculations, scoring, filters and alert conditions.
3. Identify how GSE defines:
   - Support and resistance (SNR).
   - Level freshness, touches, strength and invalidation.
   - Break of Structure (BOS) and Change of Character (CHoCH).
   - Liquidity sweeps and swing highs/lows.
   - Role reversal and flipped levels.
   - Higher-timeframe alignment.
   - Displacement, volatility and opposing-level space.
   - Setup qualification, A+ thresholds and storyline states.
4. Map every condition that can reject a candidate setup.
5. Identify repainting, look-ahead bias, future leakage, duplicate signals and performance bottlenecks.

Deliverable: GSE_BASELINE_AUDIT.md, documenting the real existing implementation rather than assumptions.

Do not modify the baseline during this phase.

3. Phase 2 — Build the research architecture

Use Python for research and backtesting. Keep the live TradingView indicator separate.

Recommended architecture:

- data/ — historical market data and data validation.
- gse_research/structure.py — SNR, swing points and structural events.
- gse_research/signals.py — candidate setups and entry rules.
- gse_research/backtest.py — trade simulation and execution assumptions.
- gse_research/metrics.py — performance statistics.
- gse_research/experiments.py — controlled hypothesis testing.
- tests/ — unit tests, regression tests and anti-look-ahead checks.
- results/ — experiment results, charts and reports.
- config/ — reproducible parameters and experiment settings.

Inspect the existing repository first and adapt this structure to the project instead of duplicating existing components.

Use versioned configurations and preserve a reproducible record of every experiment.

4. Phase 3 — Historical gold dataset

Start with XAU/USD historical OHLCV data covering ideally 2–5 years, subject to actual data availability and quality.

Prioritize:

- 4H candles for major market structure.
- 1H candles for directional context.
- 15M candles for setup construction.
- Optional 5M and 1M candles for execution research.

Requirements:

- Align all timeframes and timestamps correctly.
- Account for timezone, daylight-saving changes and trading sessions.
- Document the broker/data provider and its limitations.
- Detect missing candles, duplicates and bad prices.
- Do not assume tick volume represents centralized traded volume.
- Use only information available at the time each signal occurred.

Store data locally in an efficient format such as Parquet.

Do not fabricate missing historical data. If suitable data is unavailable, implement the pipeline and clearly report what is needed.

5. Phase 4 — Establish the baseline

Reproduce GSE v4.0 behaviour as closely as the source code and available data allow.

Record each candidate setup, including:

- Timestamp and direction.
- Timeframe and market session.
- Relevant SNR levels and their age.
- Number of touches and level status.
- BOS/CHoCH confirmation.
- Liquidity sweep status.
- Role reversal.
- 1H and 4H structural alignment.
- ATR and volatility regime.
- Distance to opposing structure.
- Every score, filter and rejection reason.
- Entry, stop loss, take profit and outcome, where defined by the actual strategy.

If the indicator does not define an objective entry or exit, document the gap and create an explicitly labelled research execution model. Do not pretend that a simulated strategy exactly reproduces the indicator.

Deliverable: Baseline trade log, metrics report and a summary of candidate rejection reasons.

6. Phase 5 — Research the hypotheses individually

Run controlled experiments that change one rule at a time.

Priority experiments

R001 — Liquidity sweep requirement
Compare mandatory sweep, optional sweep, sweep as a scoring factor and context-dependent sweep requirements.

R002 — SNR freshness
Test level age, touch count, repeated tests and whether fresh levels actually outperform tested levels.

R003 — Role reversal
Measure whether a broken resistance becoming support, or support becoming resistance, improves subsequent outcomes.

R004 — BOS versus CHoCH
Compare their predictive value and determine whether either should be mandatory.

R005 — Multi-timeframe alignment
Compare 15M-only signals against 15M + 1H and 15M + 1H + 4H context.

R006 — Trading sessions
Compare Asia, London and New York, accounting for overlapping sessions and seasonal time changes.

R007 — Opposing-level space
Test whether minimum available price space improves achievable R multiples and reduces premature targets.

R008 — Displacement quality
Test objective candle range, ATR-normalized displacement and follow-through.

R009 — Level scoring
Compare individual structural features and combinations without double-counting correlated evidence.

R010 — A+ qualification
Test whether the current threshold is appropriate and whether a different threshold improves out-of-sample expectancy.

For each experiment, state the hypothesis, control, variable, sample size, metrics, limitations and conclusion.

Do not combine all proposed changes into one experiment.

7. Phase 6 — Backtesting and statistical validation

Calculate at minimum:

- Number of trades and setups per week/month.
- Win rate.
- Average winning and losing R.
- Expectancy per trade in R.
- Profit factor.
- Maximum drawdown.
- MAE and MFE.
- Results by session, direction and timeframe.
- Signal frequency and rejected-candidate breakdown.
- Trading costs, spread, slippage and sensitivity to execution assumptions.

Use a chronological split:

- Training period for developing hypotheses.
- Validation period for selecting candidate changes.
- Untouched out-of-sample period for final evaluation.

Add walk-forward testing where practical.

Prevent look-ahead bias, including when confirming swing points, detecting breakouts and using higher-timeframe candles that have not yet closed.

Model realistic entry timing, stop/target sequencing and transaction costs. Where candle data cannot determine which level was hit first, use finer-grained data or a conservative assumption.

Do not optimize exclusively for win rate. Prefer robust expectancy and drawdown characteristics over an attractive historical curve.

8. Phase 7 — Diagnose missing setups

GSE must explain why a candidate was rejected instead of silently displaying nothing.

Build a rejection funnel such as:

Candidate → Valid SNR → HTF context → BOS/CHoCH → Sweep → Space → Score threshold → Qualified setup.

Record the exact stage and reason for every rejection.

Create a report showing the number and percentage of candidates eliminated by each rule, plus the outcomes of comparable candidates that passed and failed that rule.

The goal is to identify unnecessary restrictions without removing filters that provide genuine value.

9. Phase 8 — Research dashboard

Build a lightweight local dashboard or report that displays:

- Baseline versus experimental performance.
- Equity and drawdown curves.
- Trade distribution by session and timeframe.
- Feature-level performance comparisons.
- Candidate rejection funnel.
- Sample sizes and uncertainty.
- Experiment configuration and dataset version.

Show both absolute performance and the difference versus baseline.

Do not present a feature score as a probability of winning unless that probability has been calibrated and independently validated.

10. Phase 9 — Improve GSE architecture

Keep the research system modular:

GSE Core: Objective structural events and levels.

GSE Research: Dataset creation, hypothesis testing and backtesting.

GSE Scoring: Evidence-based confluence and calibrated probabilities where justified.

GSE Live: TradingView visualization, actionable states and alerts.

The eventual live workflow should communicate three clear states:

1. STORYLINE — Market context and directional structure.
2. WATCH — A potential setup is developing, with missing conditions explained.
3. A+ SETUP — All required conditions are satisfied.

A WATCH state is informational, not an instruction to enter a trade.

Do not port unvalidated research rules into the live indicator. Preserve the existing version so results remain comparable.

11. Definition of success

GSE Engineering Research is successful when it can:

- Reproduce a documented baseline.
- Explain every candidate’s qualification or rejection.
- Test individual rules without changing unrelated variables.
- Produce reproducible results with realistic costs.
- Validate changes on unseen historical data.
- Identify which rules improve expectancy, drawdown or signal quality.
- Recommend changes supported by evidence, including when the conclusion is to keep the current rule.

There is no requirement to generate more trades or achieve a predetermined win rate.

12. Claude Code execution instructions

Work incrementally and inspect the repository before implementation.

Start by producing the baseline audit and an implementation plan. Then implement the data pipeline, baseline reproduction, metrics and first experiment in separate stages.

After each stage:

- Run automated tests.
- Check for future-data leakage and repainting assumptions.
- Save results and document limitations.
- Report changed files and commands used.
- Ask for additional data only when it is genuinely necessary.

Do not overwrite the existing GSE v4.0 source. Do not publish a new TradingView version automatically. Do not claim that a strategy is profitable without reproducible evidence.

First task

Begin with Phase 1 only. Inspect the available repository, identify the actual GSE v4.0 source and its dependencies, produce GSE_BASELINE_AUDIT.md, and propose the smallest implementation plan for Research Experiment R001: whether requiring a liquidity sweep improves 15M XAU/USD setups when 1H and 4H structure are considered.

Do not begin changing the live strategy until the audit is complete and the baseline can be tested.
