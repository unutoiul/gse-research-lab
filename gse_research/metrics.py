"""Performance statistics in R, and uncertainty by a weekly block bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd


COLUMNS = ["entry_time", "R", "mfe_R", "mae_R", "planned_rr", "bars_held", "reason", "spread_R"]


def closed(trades: pd.DataFrame) -> pd.DataFrame:
    """Trades that entered and exited (no-entry, invalid and still-open rows are excluded)."""
    if trades.empty or "R" not in trades:
        return pd.DataFrame(columns=COLUMNS)
    return trades[trades["R"].notna()]


def max_drawdown(r: pd.Series) -> float:
    """Largest peak-to-trough fall of cumulative R, trades in entry order."""
    if r.empty:
        return 0.0
    equity = r.cumsum()
    peak = np.maximum.accumulate(np.r_[0.0, equity.to_numpy()])[1:]
    return float((peak - equity.to_numpy()).max())


def summarize(trades: pd.DataFrame, weeks: float | None = None) -> dict:
    t = closed(trades).sort_values("entry_time")
    r = t["R"]
    wins, losses = r[r > 0], r[r <= 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    out = {
        "trades": int(len(r)),
        "win_rate": float((r > 0).mean()) if len(r) else np.nan,
        "avg_win_R": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss_R": float(losses.mean()) if len(losses) else np.nan,
        "expectancy_R": float(r.mean()) if len(r) else np.nan,
        "total_R": float(r.sum()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else (np.inf if gross_win > 0 else np.nan),
        "max_drawdown_R": max_drawdown(r),
        "avg_mfe_R": float(t["mfe_R"].mean()) if len(t) else np.nan,
        "avg_mae_R": float(t["mae_R"].mean()) if len(t) else np.nan,
        "median_planned_rr": float(t["planned_rr"].median()) if len(t) else np.nan,
        # One spread (buy at the ask, sell at the bid), in R: the cost every trade pays before slippage.
        "avg_spread_R": float(t["spread_R"].mean()) if len(t) and "spread_R" in t else np.nan,
        "avg_bars_held": float(t["bars_held"].mean()) if len(t) else np.nan,
    }
    # Risk statistics: SQN = sqrt(N) x mean / std of R per trade (Van Tharp's System Quality Number).
    std = float(r.std(ddof=1)) if len(r) > 1 else np.nan
    out["std_R"] = std
    out["sqn"] = float(np.sqrt(len(r)) * r.mean() / std) if len(r) > 1 and std > 0 else np.nan
    out["max_consecutive_losses"] = _longest_run(r <= 0)
    out["recovery_factor"] = float(r.sum() / out["max_drawdown_R"]) if out["max_drawdown_R"] > 0 else np.nan
    if weeks:
        out["trades_per_week"] = len(r) / weeks
        out["trades_per_month"] = len(r) / weeks * 52 / 12
        out["R_per_year"] = float(r.sum() / weeks * 52)
    if len(t):
        for reason, n in t["reason"].value_counts().items():
            out[f"exit_{reason}"] = int(n)
    return out


def _longest_run(flags: pd.Series) -> int:
    best = cur = 0
    for f in flags.to_numpy():
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return int(best)


def bootstrap_mean(trades: pd.DataFrame, n: int = 2000, seed: int = 7, level: float = 0.90) -> dict:
    """Interval for the mean R per trade, resampling calendar weeks (trades in a week move together)."""
    t = closed(trades)
    if len(t) < 2:
        return {"low": np.nan, "high": np.nan}
    wk = t["entry_time"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("W").astype(str)
    g = t.groupby(wk)["R"].agg(["sum", "count"]).to_numpy()
    idx = np.random.default_rng(seed).integers(0, len(g), size=(n, len(g)))
    s, c = g[idx, 0].sum(1), g[idx, 1].sum(1)
    means = s[c > 0] / c[c > 0]
    lo, hi = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {"low": float(lo), "high": float(hi)}


# Verdict rules, fixed before any result is read. A result is never "deployable" here:
# the best possible status, "candidate", still needs the locked test period and the parity gate.
MIN_TRADES = 100
MIN_PROFIT_FACTOR = 1.2


def verdict(summary: dict, ci_low: float | None, in_sample: bool) -> dict:
    n, e, pf = summary.get("trades", 0), summary.get("expectancy_R", np.nan), summary.get("profit_factor", np.nan)
    if n < MIN_TRADES:
        return {"status": "inconclusive", "label": "Inconclusive", "reasons": [f"{n} trades; at least {MIN_TRADES} are needed"]}
    if not e > 0:
        return {"status": "rejected", "label": "Rejected",
                "reasons": [f"expectancy {e:+.3f} R per trade after costs" + (" (in-sample)" if in_sample else " out of sample")]}
    if in_sample:
        return {"status": "in_sample", "label": "In-sample only",
                "reasons": ["positive on training data only; run it on the validation period"]}
    reasons = []
    if ci_low is not None and not ci_low > 0:
        reasons.append(f"90% interval of the expectancy reaches {ci_low:+.3f} R (includes zero)")
    if not pf >= MIN_PROFIT_FACTOR:
        reasons.append(f"profit factor {pf:.2f} < {MIN_PROFIT_FACTOR}")
    if reasons:
        return {"status": "watch", "label": "Watch", "reasons": reasons}
    return {"status": "candidate", "label": "Candidate",
            "reasons": ["positive out of sample with a margin; next: locked test period and the TradingView parity check"]}


def by_group(trades: pd.DataFrame, column: str) -> pd.DataFrame:
    t = closed(trades)
    rows = {key: summarize(g) for key, g in t.groupby(column)}
    cols = ["trades", "win_rate", "expectancy_R", "total_R", "profit_factor", "max_drawdown_R", "avg_mfe_R", "avg_mae_R"]
    return pd.DataFrame(rows).T.reindex(columns=cols)


def bootstrap_mean_diff(a: pd.DataFrame, b: pd.DataFrame, n: int = 2000, seed: int = 7,
                        level: float = 0.90) -> dict:
    """Interval for mean R(b) - mean R(a), resampling calendar weeks (paired: both arms share the weeks)."""
    ta, tb = closed(a), closed(b)
    if ta.empty or tb.empty:
        return {"diff": np.nan, "low": np.nan, "high": np.nan, "resamples": 0}
    wk = lambda t: t["entry_time"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("W").astype(str)
    ga = ta.groupby(wk(ta))["R"].agg(["sum", "count"])
    gb = tb.groupby(wk(tb))["R"].agg(["sum", "count"])
    weeks = sorted(set(ga.index) | set(gb.index))
    A = ga.reindex(weeks, fill_value=0).to_numpy()
    B = gb.reindex(weeks, fill_value=0).to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(weeks), size=(n, len(weeks)))
    sa, ca = A[idx, 0].sum(1), A[idx, 1].sum(1)
    sb, cb = B[idx, 0].sum(1), B[idx, 1].sum(1)
    ok = (ca > 0) & (cb > 0)
    diffs = sb[ok] / cb[ok] - sa[ok] / ca[ok]
    lo, hi = np.quantile(diffs, [(1 - level) / 2, 1 - (1 - level) / 2]) if len(diffs) else (np.nan, np.nan)
    return {"diff": float(tb["R"].mean() - ta["R"].mean()), "low": float(lo), "high": float(hi), "resamples": int(ok.sum())}
