"""One-shot test of a frozen rule on the locked test period (2023+). Owner approval required.

The rule and its pass criteria are committed first (results/<name>/rule.json and
PREREGISTRATION.md). The run then:
1. builds the rule's signals over the whole history in one pass (2015-10 .. test end),
2. reproduces the rule's recorded validation result with this code; on any mismatch it
   stops before the test period is touched,
3. simulates the test period once at three cost levels and judges it by the frozen criteria.
It refuses to run twice, and refuses with uncommitted code or rule changes.

    python -m gse_research locked-test results/X1/rule.json --allow-test
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics
from . import msnr_search as ms
from . import strategy as st

WARMUP, D1_WARMUP = "2015-10-01", "2015-01-01"
MIN_TRADES = 100


def judge(net: dict, ci_low: float, years: dict[int, float]) -> dict:
    """The frozen criteria (PREREGISTRATION.md)."""
    n, e, pf = net.get("trades") or 0, net.get("expectancy_R"), net.get("profit_factor")
    positive = sum(1 for v in years.values() if v is not None and v == v and v > 0)
    checks = {"trades >= 100": n >= MIN_TRADES, "net expectancy > 0": e is not None and e > 0,
              "bootstrap lower bound > 0": ci_low is not None and ci_low > 0,
              "profit factor >= 1.2": pf is not None and pf >= metrics.MIN_PROFIT_FACTOR,
              f"positive in >= 3 of {len(years)} years": positive >= 3}
    if not checks["trades >= 100"]:
        status = "inconclusive"
    elif not checks["net expectancy > 0"]:
        status = "fail"
    elif all(checks.values()):
        status = "pass"
    else:
        status = "weak"
    return {"status": status, "checks": checks, "years_positive": positive}


def _signals(rule: dict, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    hist = data.load("M15", start=D1_WARMUP, end=end)
    m15 = hist[hist["time"] >= pd.Timestamp(WARMUP, tz="UTC")].reset_index(drop=True)
    tf = rule["chart_tf"]
    chart = m15 if tf == "15m" else data.aggregate(m15, tf)
    p = ms._params(rule)
    sig = st.signals(chart, p, st.h1_inputs(chart, p), st.h4_inputs(chart, st.StrategyParams()))
    masks = ms.filter_masks(sig, st.d1_inputs(chart, p, hist), ms.higher_bias(chart, tf, p, hist),
                            ms.range_mid(chart, int(rule["swing_len"])))
    keep = sig["signal"].to_numpy(bool).copy()
    for f in ms.FILTERS:
        if rule[f]:
            keep &= masks[f]
    return chart, sig.assign(signal=keep)


def _years(trades: pd.DataFrame, years: list[int]) -> dict[int, float]:
    closed = metrics.closed(trades)
    by = closed.groupby(closed["exit_time"].dt.year)["R"].mean() if len(closed) else pd.Series(dtype=float)
    return {y: (float(by[y]) if y in by.index else None) for y in years}


def run(rule_path: Path, allow_test: bool = False) -> Path:
    if not allow_test:
        raise SystemExit("The test period is locked. Opening it needs the owner's approval: pass --allow-test.")
    out = rule_path.parent
    if (out / "summary.json").exists():
        raise SystemExit(f"{out.name} has already been tested. The test period is one-shot.")
    git = experiments._git()
    if git["dirty"]:
        raise SystemExit("Commit the code first: the run must name the exact code that produced it.")
    spec = json.loads(rule_path.read_text(encoding="utf-8"))
    rule, (a, b) = spec["rule"], spec["test_period"]
    chart, sig = _signals(rule, str((pd.Timestamp(b) + pd.Timedelta(days=2)).date()))

    # 1. Same rule, same code: the recorded validation result must come back exactly.
    rec = spec["recorded"]["validation"]
    vt, _ = st.simulate(chart, sig, *rec["period"], ms.COSTS["net"])
    vs = metrics.summarize(vt)
    if vs.get("trades") != rec["trades"] or not abs(vs.get("expectancy_R", np.nan) - rec["expectancy_R"]) < 1e-9:
        raise SystemExit(f"Validation not reproduced ({vs.get('trades')} trades, {vs.get('expectancy_R')} R; recorded "
                         f"{rec['trades']}, {rec['expectancy_R']}). The test period was not opened.")

    # 2. The test period, once.
    weeks = (pd.Timestamp(b) - pd.Timestamp(a)).days / 7
    results, trades_net = {}, None
    for cost, broker in ms.COSTS.items():
        trades, counts = st.simulate(chart, sig, a, b, broker)
        results[cost] = {**metrics.summarize(trades, weeks), "orders": counts}
        if cost == "net":
            trades_net = trades
    ci = metrics.bootstrap_mean(metrics.closed(trades_net), level=0.90)
    years = _years(trades_net, spec["test_years"])
    verdict = judge(results["net"], ci["low"], years)
    summary = {"name": spec["name"], "rule": rule, "test_period": [a, b], "validation_reproduced": True,
               "results": results, "ci90": ci, "years_R": years, "verdict": verdict,
               "provenance": {"git": git, "dataset_sha256": json.loads(data.MANIFEST.read_text())[
                   data.dataset_path("M15").name]["sha256"]}}
    trades_net.to_csv(out / "trades_net.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(report(spec, summary), encoding="utf-8")
    return out


def report(spec: dict, s: dict) -> str:
    fmt = experiments._fmt
    r, rec, v = s["results"], spec["recorded"], s["verdict"]
    label = {"pass": "PASS", "weak": "WEAK", "fail": "FAIL", "inconclusive": "INCONCLUSIVE"}[v["status"]]
    rows = [("Train 2016–2018", rec["train"]["trades"], rec["train"]["expectancy_R"], "", ""),
            ("Validation 2019–2022", rec["validation"]["trades"], rec["validation"]["expectancy_R"], "", ""),
            ("**Test 2023–2026**", r["net"].get("trades"), r["net"].get("expectancy_R"), r["net"].get("profit_factor"),
             r["net"].get("win_rate"))]
    lines = [f"# {spec['name']} — locked test result: {label}", "",
             f"> {experiments.PROVISIONAL}", "",
             f"Rule frozen {spec['frozen']} (PREREGISTRATION.md, rule.json). Test period {s['test_period'][0]} to "
             f"{s['test_period'][1]}, opened once. The recorded validation result was reproduced exactly first.", "",
             f"Git `{s['provenance']['git']['commit'][:10]}` · dataset `{s['provenance']['dataset_sha256'][:12]}…`", "",
             "## Result (OANDA costs)", "",
             "| Period | Trades | Expectancy (R) | Profit factor | Win rate |", "|---|---|---|---|---|",
             *[f"| {p} | {n} | {fmt(e)} | {fmt(pf) if pf != '' else '–'} | {fmt(w) if w != '' else '–'} |" for p, n, e, pf, w in rows],
             "",
             f"Test, other cost levels: half spread {fmt(r['half'].get('expectancy_R'))} R, before costs "
             f"{fmt(r['gross'].get('expectancy_R'))} R. 90% interval of the net expectancy: {fmt(s['ci90']['low'])} to "
             f"{fmt(s['ci90']['high'])} R. Max drawdown {fmt(r['net'].get('max_drawdown_R'))} R.", "",
             "By year (net, R per trade): " + ", ".join(f"{y} {fmt(x)}" for y, x in s["years_R"].items()) + ".", "",
             "## Frozen criteria", "",
             *[f"- {'✔' if ok else '✘'} {name}" for name, ok in v["checks"].items()], "",
             f"**{label}.** " + {
                 "pass": "The rule made money on years it had never seen, by every frozen criterion. A candidate: the "
                         "TradingView parity check and live paper trading come next, before any real money.",
                 "weak": "Positive on the unseen years, but not by every frozen criterion: not evidence of an edge.",
                 "fail": "The rule lost money on the years it had never seen. Its 2019–2022 result was luck from picking "
                         "the best of 5,064 combinations.",
                 "inconclusive": "Too few trades on the unseen years to judge.",
             }[v["status"]], "",
             "The test period is now spent: no other rule can be judged on it.", ""]
    return "\n".join(lines)
