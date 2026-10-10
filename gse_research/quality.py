"""Data quality of the M15 cache: issue list, per-year report and markdown report.

A gold trading day (18:00 to 17:00 New York) has 92 fifteen-minute candles.
Issues are facts about the feed to review, not automatic deletions:

- error: duplicate or misaligned time, inconsistent OHLC, non-positive price,
  crossed quote (bid above ask), a traded candle inside the daily 17:00-18:00
  New York break or the weekend. These break the session model or the cost model.
- review: a price jump or candle range far above the recent typical range, or a
  1-2 tick print outside the session (`break_print`, `weekend_print`), which
  TradingView's session leaves out and `data.load()` drops.

Thin candles (1 or 2 ticks) and flat candles (no range) mean the feed had too
few prices to show real structure; they are counted per year, not listed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data import STEP, session_clock

CANDLES_PER_DAY = 92
JUMP_MULT = 15.0  # x rolling median candle range
ERRORS = ("duplicate", "misaligned", "ohlc", "nonpositive", "crossed", "break", "weekend")


def _ohlc_bad(df: pd.DataFrame, prefix: str = "") -> pd.Series:
    o, h, l, c = (df[f"{prefix}{k}"] for k in ("open", "high", "low", "close"))
    return (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)


def issues(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (candle, issue kind): time, kind, severity, detail."""
    step = STEP["M15"]
    t = df["time"]
    clock = session_clock(t)
    found: list[pd.DataFrame] = []

    def add(mask: pd.Series, kind: str, detail: pd.Series | str) -> None:
        mask = mask.fillna(False)
        if mask.any():
            d = detail[mask] if isinstance(detail, pd.Series) else detail
            found.append(pd.DataFrame({"time": t[mask], "kind": kind, "detail": d}))

    add(t.duplicated(keep=False), "duplicate", "same open time")
    add(t.diff() <= pd.Timedelta(0), "misaligned", "time not increasing")
    add((t - t.dt.floor("15min")) != pd.Timedelta(0), "misaligned", "not on the 15-minute grid")
    for prefix, name in (("", "mid"), ("bid_", "bid"), ("ask_", "ask")):
        add(_ohlc_bad(df, prefix), "ohlc", f"{name} high/low do not contain open/close")
    prices = df[[c for c in df.columns if c.endswith(("open", "high", "low", "close")) and c != "close_time"]]
    add((prices <= 0).any(axis=1), "nonpositive", "price <= 0")
    crossed = (df["bid_open"] > df["ask_open"]) | (df["bid_close"] > df["ask_close"])
    add(crossed, "crossed", "bid above ask at open or close")
    # Outside TradingView's gold session. A 1-2 tick candle there is a stray
    # closing print (review); real trading there means the session differed.
    thin = df["volume"] <= 2
    for mask, kind, where in ((clock.dt.hour == 23, "break", "inside the 17:00-18:00 New York break"),
                              (clock.dt.dayofweek >= 5, "weekend", "between Friday 17:00 and Sunday 18:00 New York")):
        add(mask & ~thin, kind, where)
        add(mask & thin, f"{kind}_print", f"1-2 tick print {where}")

    # Jumps: a gap from the previous close, or a candle range, far above the
    # recent typical range. Gaps across the daily break and weekends are normal.
    rng = df["high"] - df["low"]
    typical = rng.rolling(96, min_periods=20).median().shift()
    day = clock.dt.floor("D")
    same_day = day.eq(day.shift()) & (t.diff() == step)
    gap = (df["open"] - df["close"].shift()).abs()
    add(same_day & (gap > JUMP_MULT * typical) & (typical > 0), "jump",
        "open gap " + gap.round(2).astype(str) + " vs typical range " + typical.round(2).astype(str))
    add((rng > JUMP_MULT * typical) & (typical > 0), "spike",
        "range " + rng.round(2).astype(str) + " vs typical range " + typical.round(2).astype(str))

    if not found:
        return pd.DataFrame({"time": pd.Series(dtype=t.dtype), "kind": pd.Series(dtype=str),
                             "severity": pd.Series(dtype=str), "detail": pd.Series(dtype=str)})
    out = pd.concat(found, ignore_index=True).sort_values(["time", "kind"], ignore_index=True)
    out["severity"] = np.where(out["kind"].isin(ERRORS), "error", "review")
    return out[["time", "kind", "severity", "detail"]]


def missing_slots(df: pd.DataFrame) -> pd.DataFrame:
    """Per trading day: candles present, interior missing slots, first and last candle (New York)."""
    t = df["time"]
    clock = session_clock(t)
    frame = pd.DataFrame({"time": t, "day": clock.dt.floor("D"), "ny": t.dt.tz_convert("America/New_York")})
    frame["interior_missing"] = ((t.diff() / STEP["M15"]) - 1).where(frame["day"].eq(frame["day"].shift()), 0).clip(lower=0)
    g = frame.groupby("day")
    out = g.agg(candles=("time", "size"), interior_missing=("interior_missing", "sum"), first=("ny", "first"), last=("ny", "last"))
    out["interior_missing"] = out["interior_missing"].astype(int)
    return out


def year_report(df: pd.DataFrame, found: pd.DataFrame | None = None) -> pd.DataFrame:
    found = issues(df) if found is None else found
    days = missing_slots(df)
    days["year"] = days.index.year
    found = found.assign(year=found["time"].dt.year)
    y_issue = found.groupby(["year", "kind"]).size().unstack(fill_value=0)
    y_error = found[found["severity"] == "error"].groupby("year").size()
    frame = df.assign(year=df["time"].dt.year, range=df["high"] - df["low"], spread=df["ask_close"] - df["bid_close"])
    rows = []
    for year, y in frame.groupby("year"):
        d = days[days["year"] == year]
        coverage = len(y) / (len(d) * CANDLES_PER_DAY)
        thin = (y["volume"] <= 2).mean()
        spread, rng = y["spread"].median(), y["range"].median()
        counts = {k: int(y_issue.at[year, k]) if year in y_issue.index and k in y_issue.columns else 0
                  for k in ("jump", "spike", "break_print", "weekend_print")}
        errors = int(y_error.get(year, 0))
        verdict = (
            "check" if errors
            else "good" if coverage >= 0.95 and thin <= 0.05
            else "usable" if coverage >= 0.85 and thin <= 0.20
            else "thin"
        )
        rows.append({
            "year": year,
            "candles": len(y),
            "trading_days": len(d),
            "full_days": int((d["candles"] == CANDLES_PER_DAY).sum()),
            "coverage": round(coverage, 3),
            "interior_missing": int(d["interior_missing"].sum()),
            "thin_candles": round(thin, 3),
            "flat_candles": round((y["range"] == 0).mean(), 3),
            "errors": errors,
            "prints": counts["break_print"] + counts["weekend_print"],
            "jumps": counts["jump"] + counts["spike"],
            "median_spread": round(spread, 3),
            "p90_spread": round(y["spread"].quantile(0.9), 3),
            "median_range": round(rng, 2),
            "cost_ratio": round(spread / rng, 3) if rng else None,
            "median_price": round(y["close"].median(), 1),
            "verdict": verdict,
        })
    return pd.DataFrame(rows).set_index("year")


def _table(frame: pd.DataFrame) -> str:
    cols = [frame.index.name or "", *frame.columns]
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, row in frame.iterrows():
        lines.append("| " + " | ".join(map(str, [idx, *row.tolist()])) + " |")
    return "\n".join(lines)


def write_report(df: pd.DataFrame, manifest: dict, out_dir: Path) -> tuple[Path, pd.DataFrame]:
    """Write the markdown report and the full issue list (CSV); return the path and the per-year table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    found = issues(df)
    report = year_report(df, found)
    stem = Path(manifest["file"]).stem
    found.to_csv(out_dir / f"{stem}_issues.csv", index=False)
    by_kind = found.groupby(["kind", "severity"]).size().rename("count").reset_index().set_index("kind")
    days = missing_slots(df)
    opens = days["first"].dt.strftime("%H:%M").value_counts().head(5)
    closes = days["last"].dt.strftime("%H:%M").value_counts().head(5)
    text = f"""# Data quality: {manifest['file']}

Generated by `python -m gse_research quality`. Do not edit by hand.

| Dataset | |
|---|---|
| Provider | {manifest['provider']} ({manifest['environment']}) |
| Instrument, granularity | {manifest['instrument']} {manifest['granularity']} |
| Prices | {manifest['price']} |
| Volume | {manifest['volume']} |
| Candles | {manifest['rows']:,}, opens {manifest['first_open']} to {manifest['last_open']} |
| SHA-256 | `{manifest['sha256']}` |
| Downloaded | {manifest['downloaded_at']} |

## Per year

Coverage = candles / (trading days x {CANDLES_PER_DAY}); above 1 means candles outside the session. Interior missing = 15-minute slots missing between two candles of the same trading day. Thin = 1-2 ticks. Errors = error-level issues. Prints = 1-2 tick candles outside the session (dropped by `data.load()`). Jumps = jumps and spikes to review. Spread = ask - bid at the candle close. Cost ratio = median spread / median candle range. Verdict: `check` if the year has any error-level issue, then `good` (coverage >= 0.95, thin <= 0.05), `usable` (>= 0.85, <= 0.20) or `thin`.

{_table(report)}

## Issues by kind

Full list: `{stem}_issues.csv`.

{_table(by_kind) if len(by_kind) else 'None.'}

## Session shape (New York time)

Most common first candle of a trading day: {', '.join(f'{k} ({v:,})' for k, v in opens.items())}.
Most common last candle: {', '.join(f'{k} ({v:,})' for k, v in closes.items())}.
"""
    path = out_dir / f"{stem}.md"
    path.write_text(text, encoding="utf-8")
    return path, report
