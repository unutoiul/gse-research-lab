"""Study E1: do GSE's levels have any edge at all, before costs and before any trade rule?

For every first touch of a fresh level, and every first touch of a confirmed flipped level after its
confirming retest (GSE v4.1 levels, FRESH_FLIP_TOUCH_SPEC.md), measured from the level price:
- does price reach 1 ATR in the level's direction (away from it) before 1 ATR against it, within 32 candles?
- the move after 4 / 8 / 16 / 32 candles, in ATR (the chart's ATR(14) at the close before the touch).
The same is measured for random levels: each real touch gets CONTROLS random levels on the same side, at
the same distance from price (in ATR) as the real level had when it formed, starting at random candles of
the same period, first touched the same way. If GSE's levels mean something, price turns away from them
more often than from random prices.

The touch candle itself: its adverse extreme counts (a candle that reaches the level and runs 1 ATR
through it is a loss), its favourable extreme does not (it may come before the touch). Real and random
levels are treated alike. A touch from a gap through the level is skipped.

Cells: chart 15m / 1H / 4H x swing lookback 3 / 5 / 10 x fresh / flipped. Train (2016-2018) and validation
(2019-2022) are reported separately; an edge has to show in both. The intervals are widened for the 18
cells. The test period is not used.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, resources, structure
from . import strategy as st
from .structure import ST_FLIP, ST_FRESH

CHARTS, LOOKBACKS, TYPES = ["15m", "1H", "4H"], [3, 5, 10], ["fresh", "flipped"]
HORIZONS, K_ATR, MAX_BARS, CONTROLS, SEED = [4, 8, 16, 32], 1.0, 32, 3, 20261015
WARMUP, DATA_END = "2015-10-01", "2023-01-03"
PERIODS = {"train": ("2016-01-01", "2019-01-01"), "val": ("2019-01-01", "2023-01-01")}
SLIPPAGE = 0.10   # price units, as in every strategy study
IND_LEN, IND_AGE = 3, 10

_M15: pd.DataFrame | None = None


def _init() -> None:
    global _M15
    _M15 = data.load("M15", start=WARMUP, end=DATA_END)


def _chart(tf: str) -> pd.DataFrame:
    return _M15 if tf == "15m" else data.aggregate(_M15, tf)


def touch_events(chart: pd.DataFrame, swing: int) -> tuple[pd.DataFrame, np.ndarray]:
    """First touches of fresh and newly confirmed flipped levels, with the ATR series.

    A level is watched from the close after it formed (or was confirmed), while price is away from it
    (alerts.pine watch list). A touch is a candle whose range reaches it, opened on the level's side."""
    O, H, L = (chart[k].to_numpy(float) for k in ("open", "high", "low"))
    core = structure.CoreParams(swing_len=swing, **structure.V41_FLIPS)
    prev: list[tuple] = []
    rows: list[dict] = []
    lows, highs = st.minor_swings(chart, IND_LEN, True), st.minor_swings(chart, IND_LEN, False)

    def hook(t, levels, eqh, eql, pdh, pdl, pwh, pwl, atr, c):
        nonlocal prev
        for lid, price, role, kind, born, after in prev:
            if L[t] <= price <= H[t] and role * (O[t] - price) >= 0:
                state, age = st.inducement(lows if role == 1 else highs, role, price, after, t - 1, t - 1)
                rows.append({"bar": t, "level_id": lid, "price": price, "side": role, "type": kind, "born_bar": born,
                             "ind_state": state, "ind_sweep_age": age})
        prev = [(lv.id, lv.price, lv.role, "fresh" if lv.state == ST_FRESH else "flipped", lv.born_bar,
                 lv.born_bar if lv.state == ST_FLIP else lv.origin_bar)
                for lv in levels if not lv.in_contact and (lv.state == ST_FRESH or (lv.state == ST_FLIP and lv.touches == 1))]

    out, _ = structure.run(chart, core, hook=hook)
    return pd.DataFrame(rows), out["atr"].to_numpy(float)


def outcomes(chart: pd.DataFrame, ev: pd.DataFrame, atr: np.ndarray) -> pd.DataFrame:
    """For each touch (bar, price, side): first passage of +/-K_ATR and the move after each horizon."""
    H, L, C = (chart[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(C)
    res = {k: np.full(len(ev), np.nan) for k in ["atr", "win", "mfe", "mae", *[f"ret_{h}" for h in HORIZONS]]}
    for i, (t, p, d) in enumerate(zip(ev["bar"].to_numpy(int), ev["price"].to_numpy(float), ev["side"].to_numpy(int))):
        a = atr[t - 1] if t > 0 else np.nan
        if not a > 0 or t + MAX_BARS >= n:
            continue
        res["atr"][i] = a
        fav = d * ((H if d == 1 else L)[t + 1: t + MAX_BARS + 1] - p) / a
        adv = d * (p - (L if d == 1 else H)[t: t + MAX_BARS + 1]) / a   # includes the touch candle
        adv_after = adv[1:]
        res["mfe"][i], res["mae"][i] = fav.max(), adv.max()
        loss_bar = 0 if adv[0] >= K_ATR else (int(np.argmax(adv_after >= K_ATR)) + 1 if (adv_after >= K_ATR).any() else None)
        win_bar = int(np.argmax(fav >= K_ATR)) + 1 if (fav >= K_ATR).any() else None
        if loss_bar is not None and (win_bar is None or loss_bar <= win_bar):   # the same candle counts as a loss
            res["win"][i] = 0.0
        elif win_bar is not None:
            res["win"][i] = 1.0
        for h in HORIZONS:
            res[f"ret_{h}"][i] = d * (C[t + h] - p) / a
    return ev.assign(**res)


def control_events(chart: pd.DataFrame, ev: pd.DataFrame, atr: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """CONTROLS random levels per real touch: same side and distance from price at formation, a random
    start candle in the same period, then its first touch from that side (no gap through it)."""
    O, H, L, C = (chart[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    times = chart["time"]
    n = len(C)
    bounds = {p: (int(times.searchsorted(pd.Timestamp(a, tz="UTC"))), int(times.searchsorted(pd.Timestamp(b, tz="UTC"))))
              for p, (a, b) in PERIODS.items()}
    rows = []
    for e in ev.itertuples(index=False):
        dist = e.side * (C[e.born_bar] - e.price) / atr[e.born_bar]
        if not dist > 0:
            continue
        lo, hi = bounds[e.period]
        made = 0
        for _ in range(CONTROLS * 10):
            if made == CONTROLS:
                break
            b0 = int(rng.integers(lo, hi))
            if not atr[b0] > 0:
                continue
            p = C[b0] - e.side * dist * atr[b0]
            j, step, t = b0 + 1, 64, None
            while j < n and t is None:
                seg = (L[j:j + step] <= p) if e.side == 1 else (H[j:j + step] >= p)
                if seg.any():
                    t = j + int(np.argmax(seg))
                j, step = j + step, step * 2
            if t is None or e.side * (O[t] - p) < 0:
                continue
            rows.append({"bar": t, "price": p, "side": e.side, "type": e.type, "period": e.period, "born_bar": b0})
            made += 1
    return pd.DataFrame(rows)


def evaluate_cell(key: tuple) -> pd.DataFrame:
    """Real and random touches with outcomes for one chart and lookback (both level types)."""
    tf, swing = key
    chart = _chart(tf)
    ev, atr = touch_events(chart, swing)
    times = chart["time"]
    ev = ev.assign(time=times.iloc[ev["bar"]].reset_index(drop=True))
    ev["period"] = None
    for p, (a, b) in PERIODS.items():
        ev.loc[(ev["time"] >= pd.Timestamp(a, tz="UTC")) & (ev["time"] < pd.Timestamp(b, tz="UTC")), "period"] = p
    ev = ev[ev["period"].notna()].reset_index(drop=True)
    spread = (chart["ask_close"] - chart["bid_close"]).to_numpy(float)
    ev["cost_atr"] = (spread[ev["bar"] - 1] + 2 * SLIPPAGE) / atr[ev["bar"] - 1]   # one spread, slippage both ways
    real = outcomes(chart, ev, atr).assign(group="real")
    rng = np.random.default_rng([SEED, CHARTS.index(tf), swing])
    ctrl = control_events(chart, ev, atr, rng)
    ctrl = ctrl.assign(time=times.iloc[ctrl["bar"]].reset_index(drop=True))
    ctrl = outcomes(chart, ctrl, atr).assign(group="random")
    return pd.concat([real, ctrl], ignore_index=True).assign(chart_tf=tf, swing_len=swing)


def _diff(real: pd.DataFrame, ctrl: pd.DataFrame, col: str, level: float) -> dict:
    a = ctrl[["time", col]].dropna().rename(columns={"time": "entry_time", col: "R"})
    b = real[["time", col]].dropna().rename(columns={"time": "entry_time", col: "R"})
    return metrics.bootstrap_mean_diff(a, b, level=level)


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    level = 1 - 0.10 / (len(CHARTS) * len(LOOKBACKS) * len(TYPES))   # 90% two-sided, widened for 18 cells
    rows = []
    for (tf, swing, kind, period), g in events.groupby(["chart_tf", "swing_len", "type", "period"], sort=False):
        real, ctrl = g[g["group"] == "real"], g[g["group"] == "random"]
        w = _diff(real, ctrl, "win", level)
        r16 = _diff(real, ctrl, "ret_16", level)
        rows.append({"chart_tf": tf, "swing_len": swing, "type": kind, "period": period,
                     "touches": len(real), "random": len(ctrl),
                     "win_real": real["win"].mean(), "win_random": ctrl["win"].mean(),
                     "win_diff": w["diff"], "win_diff_low": w["low"], "win_diff_high": w["high"],
                     "unresolved": real["win"].isna().mean(),
                     "ret16_real": real["ret_16"].mean(), "ret16_random": ctrl["ret_16"].mean(),
                     "ret16_diff": r16["diff"], "ret16_diff_low": r16["low"], "ret16_diff_high": r16["high"],
                     "mfe_real": real["mfe"].mean(), "mae_real": real["mae"].mean(),
                     "cost_atr": real["cost_atr"].median()})
    return pd.DataFrame(rows)


def verdict(s: pd.DataFrame) -> pd.DataFrame:
    """Per cell: an edge needs the win-rate difference above zero, interval included, in both periods."""
    out = []
    for (tf, swing, kind), g in s.groupby(["chart_tf", "swing_len", "type"], sort=False):
        if set(g["period"]) != set(PERIODS):
            continue
        t, v = g[g["period"] == "train"].iloc[0], g[g["period"] == "val"].iloc[0]
        if t["win_diff_low"] > 0 and v["win_diff_low"] > 0:
            call = "edge"
        elif t["win_diff"] > 0 and v["win_diff"] > 0:
            call = "weak sign"
        else:
            call = "no edge"
        # A 1:1 trade with a 1 ATR stop at the level, before costs: 2p - 1 in R; costs take cost_atr R.
        gross_r = 2 * v["win_real"] - 1
        out.append({"chart_tf": tf, "swing_len": swing, "type": kind, "verdict": call,
                    "train_win_diff": t["win_diff"], "val_win_diff": v["win_diff"], "val_win_diff_low": v["win_diff_low"],
                    "val_ret16_diff": v["ret16_diff"], "val_gross_R_1to1": gross_r, "val_cost_R_1to1": v["cost_atr"],
                    "val_net_R_1to1": gross_r - v["cost_atr"]})
    return pd.DataFrame(out)


def inducement_table(events: pd.DataFrame) -> pd.DataFrame:
    """Lookback 10 (GSE's default): win rate by inducement state in front of the level, against random levels."""
    e = events[events["swing_len"] == 10]
    rows = []
    for (tf, kind, period), g in e.groupby(["chart_tf", "type", "period"], sort=False):
        real, base = g[g["group"] == "real"], g[g["group"] == "random"]["win"].mean()
        swept = (real["ind_sweep_age"] >= 0) & (real["ind_sweep_age"] <= IND_AGE)
        for name, m in (("none", real["ind_state"] == 0), ("present", real["ind_state"] == 1),
                        ("cleared", real["ind_state"] == 2), ("swept", swept)):
            rows.append({"chart_tf": tf, "type": kind, "period": period, "inducement": name, "touches": int(m.sum()),
                         "win_real": real.loc[m, "win"].mean(), "win_random": base,
                         "win_diff": real.loc[m, "win"].mean() - base})
    return pd.DataFrame(rows)


def run_study(workers: int | None = None, out_dir: Path | None = None, progress=None) -> Path:
    keys = [(tf, s) for tf in CHARTS for s in LOOKBACKS]
    workers = min(workers or resources.default_workers(), len(keys))
    parts = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as pool:
        for i, df in enumerate(pool.map(evaluate_cell, keys), 1):
            parts.append(df)
            if progress:
                progress(i / len(keys), f"{i} of {len(keys)} chart/lookback cells")
    events = pd.concat(parts, ignore_index=True)
    s = summarize(events)
    v = verdict(s)
    ind = inducement_table(events)
    out_dir = out_dir or data.ROOT / "results" / "E1"
    out_dir.mkdir(parents=True, exist_ok=True)
    s.to_csv(out_dir / "summary.csv", index=False)
    v.to_csv(out_dir / "verdicts.csv", index=False)
    ind.to_csv(out_dir / "inducement.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "charts": CHARTS, "lookbacks": LOOKBACKS,
            "types": TYPES, "horizons": HORIZONS, "k_atr": K_ATR, "max_bars": MAX_BARS, "controls": CONTROLS,
            "seed": SEED, "flip_rules": "4.1", "status": experiments.PROVISIONAL}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(s, v, ind, prov), encoding="utf-8")
    return out_dir


def report(s: pd.DataFrame, v: pd.DataFrame, ind: pd.DataFrame, prov: dict) -> str:
    md = experiments._md
    counts = v["verdict"].value_counts().to_dict()
    main = ["chart_tf", "swing_len", "type", "period", "touches", "win_real", "win_random", "win_diff", "win_diff_low",
            "win_diff_high", "ret16_real", "ret16_random", "ret16_diff", "ret16_diff_low", "cost_atr"]
    lines = [
        "# E1 — Do GSE's levels have an edge? (first touches against random levels, before costs)", "",
        f"> {prov['status']}", "",
        "Every first touch of a fresh level, and every first touch of a confirmed flipped level after its retest "
        "(GSE v4.1 levels), against random levels at the same distance from price on the same side. **win** = price "
        f"reaches {K_ATR:g} ATR away from the level before {K_ATR:g} ATR through it, within {MAX_BARS} candles (no answer "
        "in that time is left out); **ret16** = the move 16 candles later, in ATR, in the level's direction. Random walk "
        "with no edge: win ≈ 0.5 and ret16 ≈ 0. diff = real − random, with a weekly-block bootstrap interval "
        "(90%, widened for 18 cells). Train 2016–2018 and validation 2019–2022; the test period is not used.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Verdict per cell", "",
        "An **edge** needs the win-rate difference above zero, interval included, in both periods. The last three "
        "columns translate validation into a 1:1 trade at the level with a 1 ATR stop: gross R = 2 × win − 1, cost = one "
        "spread plus slippage in ATR (median), net = gross − cost.", "",
        md(v.set_index("chart_tf").round(3)), "",
        f"Cells: {', '.join(f'{n} {k}' for k, n in counts.items())}.", "",
        "## Real against random, by period", "", md(s[main].set_index("chart_tf").round(3)), "",
        "## Inducement at lookback 10 (win rate by what lay in front of the level)", "",
        md(ind.set_index("chart_tf").round(3)), "",
        "## Limitations", "",
        "- One reading of \"edge\": a symmetric 1 ATR first passage and the 16-candle move. Other distances could differ.",
        "- Random levels match side, distance and period, not the time of day or volatility regime of each real touch.",
        "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
