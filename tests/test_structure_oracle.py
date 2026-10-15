"""Parity with the Pine source: the Python port against GSE v4.0's own Pine code.

tests/oracle/pine_oracle.mjs translates `f_core_update` and `f_context_update`
from gse-website's Pine source (with the repo's own Pine-to-JS translator) and
runs them on the same candles and the same precomputed series inputs. Every
candle's level list, equal-high/low pools, structure, sweeps and Golden Zone
context must match.

What this does NOT cover: TradingView's built-ins (pivot tie rule, ATR/EMA
seeding, session time(), request.security) and feed differences. Those need
stored TradingView snapshots (Stage 4 parity gate).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from gse_research import data, structure

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = Path(os.environ.get("GSE_WEBSITE", ROOT.parent / "gse-website"))
ORACLE = ROOT / "tests" / "oracle" / "pine_oracle.mjs"

pytestmark = [
    pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache"),
    pytest.mark.skipif(not (WEBSITE / "tradingview" / "gse_4.0" / "src" / "core.pine").exists(), reason="gse-website not found"),
    pytest.mark.skipif(shutil.which("node") is None, reason="node not installed"),
]

CORE_FIELDS = ["struct_dir", "bos_bull", "bos_bear", "choch_bull", "choch_bear", "trend_score", "swing_conflict",
               "bull_sweep", "bear_sweep", "bull_sweep_q", "bear_sweep_q", "in_asian", "in_london", "in_ny"]
CTX_FIELDS = ["space_ok_bull", "space_ok_bear", "struct_ok_bull", "struct_ok_bear", "bull_bos_had_sweep", "bear_bos_had_sweep",
              "at_sup", "at_res", "long_zone", "short_zone", "rej_ok_bull", "rej_ok_bear", "vol_ok_bull", "vol_ok_bear"]


def _same(a, b) -> bool:
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None or (isinstance(b, float) and math.isnan(b))
    if isinstance(a, (bool,)) or isinstance(b, (bool,)):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9
    return a == b


def _oracle(m15, prep, tmp_path: Path, require_sweep: bool, core: structure.CoreParams = structure.CoreParams(),
            version: str = "4.0") -> list[dict]:
    payload = {k: m15[k].tolist() for k in ("open", "high", "low", "close")}
    payload["volume"] = m15["volume"].astype(float).tolist()
    for k in prep.columns:
        payload[k] = [None if (isinstance(v, float) and math.isnan(v)) else (bool(v) if isinstance(v, bool) or k.startswith(("new_", "in_")) else v)
                      for v in prep[k].tolist()]
    payload["params"] = {"swing_len": core.swing_len, "zone_count": core.zone_count, "tick": core.tick,
                         "require_sweep": require_sweep, "flip_min_touches": core.flip_min_touches,
                         "flip_decisive": core.flip_decisive, "flip_buffer_atr": core.flip_buffer_atr,
                         "flip_away_atr": core.flip_away_atr, "flip_failed_on": core.flip_failed_on}
    src, out = tmp_path / "input.json", tmp_path / "oracle.jsonl"
    src.write_text(json.dumps(payload))
    subprocess.run(["node", str(ORACLE), str(WEBSITE), str(src), str(out), version], check=True, capture_output=True, text=True)
    return [json.loads(line) for line in out.read_text().splitlines()]


V41 = structure.CoreParams(**structure.V41_FLIPS)


@pytest.mark.parametrize("start, end, require_sweep, core, version", [
    ("2016-01-01", "2016-07-01", False, structure.CoreParams(), "4.0"),
    ("2022-07-01", "2023-07-01", False, structure.CoreParams(), "4.0"),
    ("2022-07-01", "2023-07-01", True, structure.CoreParams(), "4.0"),
    # v4.1 role-reversal rules: the v4.1 Pine source with its defaults, and with lookback 3 (many flips).
    ("2016-01-01", "2016-07-01", False, V41, "4.1"),
    ("2022-07-01", "2023-07-01", False, structure.CoreParams(swing_len=3, **structure.V41_FLIPS), "4.1"),
])
def test_port_matches_pine_source_candle_by_candle(tmp_path, start, end, require_sweep, core, version):
    if not (WEBSITE / "tradingview" / f"gse_{version}" / "src" / "core.pine").exists():
        pytest.skip(f"gse-website has no gse_{version}")
    m15 = data.load("M15", start=start, end=end)
    prep = structure.prepare(m15, core)
    trace: list = []
    ctx = structure.ContextParams(require_sweep=require_sweep)
    out, events = structure.run(m15, core, ctx=ctx, prep=prep, trace=trace)
    js = _oracle(m15, prep, tmp_path, require_sweep, core, version)
    assert len(js) == len(out) == len(trace)
    zones = 0
    for t, (o, (levels, eqh, eql)) in enumerate(zip(js, trace)):
        row = out.iloc[t]
        assert len(levels) == len(o["levels"]), f"candle {t}: level count"
        for py, pine in zip(levels, o["levels"]):
            assert all(_same(a, b) for a, b in zip(py, pine)), f"candle {t}: level {py} vs Pine {pine}"
        assert eqh == o["eqh_pool"] and eql == o["eql_pool"], f"candle {t}: equal high/low pools"
        for k in CORE_FIELDS + CTX_FIELDS:
            assert _same(row[k], o[k]), f"candle {t}: {k} = {row[k]} vs Pine {o[k]}"
        for side, pine in (("sup", o["sup"]), ("res", o["res"])):
            assert _same(row[side], pine), f"candle {t}: nearest {side}"
            assert _same(None if row[f"{side}_id"] < 0 else row[f"{side}_id"], o[f"{side}_id"]), f"candle {t}: {side}_id"
        assert _same(row["gate_bull"], o["gate_fail_bull"]) and _same(row["gate_bear"], o["gate_fail_bear"]), f"candle {t}: gate"
        assert abs(row["score_bull"] - o["score_bull_pct"]) <= 0.5 and abs(row["score_bear"] - o["score_bear_pct"]) <= 0.5, f"candle {t}: score"
        assert row["story"] == o["story_state"], f"candle {t}: storyline"
        zones += bool(o["long_zone"]) + bool(o["short_zone"])
    if not require_sweep:
        assert zones > 0  # the window exercised the Golden Zone (with Require Sweep on it can be empty)
    if version == "4.1":  # the window exercised confirmed and failed flips
        kinds = {e["event"] for e in events}
        assert {structure.EVT_FLIP_TO_SUP, structure.EVT_FLIP_TO_RES, structure.EVT_FLIP_FAIL_SUP, structure.EVT_FLIP_FAIL_RES} <= kinds
