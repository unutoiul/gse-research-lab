"""OANDA XAU_USD candle cache, TradingView-style higher timeframes and HTF alignment.

Candles are stored in data/XAU_USD_<granularity>.parquet (git-ignored); later runs
only download what is missing. Each candle has mid OHLC (open, high, low, close),
bid and ask OHLC, and OANDA's tick volume (a count of price updates, not traded
volume). data/manifest.json records what was downloaded and the file's SHA-256.

Higher timeframes are built from M15 the way TradingView builds them for gold:
the trading day opens at 18:00 New York (22:00 UTC in summer, 23:00 in winter)
and closes at 17:00 New York, with a one-hour break. 4H candles start at the
day's open, so the last one is cut to 3 hours. 1H candles run on the clock hour.
Daily and weekly candles carry their nominal close time (17:00 New York).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

INSTRUMENT = "XAU_USD"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST = DATA_DIR / "manifest.json"
FIRST_AVAILABLE = "2006-01-01"  # OANDA's gold history starts 2006-03-19
STEP = {"M1": pd.Timedelta(minutes=1), "M15": pd.Timedelta(minutes=15)}
H = pd.Timedelta(hours=1)
PRICE_COLUMNS = [
    "open", "high", "low", "close",
    "bid_open", "bid_high", "bid_low", "bid_close",
    "ask_open", "ask_high", "ask_low", "ask_close",
]
TIME_DTYPE = "datetime64[ns, UTC]"

load_dotenv(ROOT / ".env")


def dataset_path(granularity: str = "M15") -> Path:
    return DATA_DIR / f"{INSTRUMENT}_{granularity}.parquet"


def _host() -> str:
    live = os.environ.get("OANDA_ENV") == "live"
    return "https://api-fxtrade.oanda.com" if live else "https://api-fxpractice.oanda.com"


def _fetch_page(session: requests.Session, granularity: str, start: pd.Timestamp) -> pd.DataFrame:
    token = os.environ.get("OANDA_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("OANDA_API_TOKEN is not set in .env")
    params = {
        "granularity": granularity,
        "price": "MBA",
        "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": 5000,
    }
    url = f"{_host()}/v3/instruments/{INSTRUMENT}/candles"
    for attempt in range(5):
        try:
            res = session.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
            continue
        if res.ok:
            break
        if res.status_code == 429 or res.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        raise SystemExit(f"OANDA {res.status_code}: {res.text}")
    else:
        raise SystemExit("OANDA kept failing; try again later")
    rows = [
        (
            c["time"],
            *(float(c[side][k]) for side in ("mid", "bid", "ask") for k in "ohlc"),
            int(c["volume"]),
        )
        for c in res.json()["candles"]
        if c["complete"]
    ]
    df = pd.DataFrame(rows, columns=["time", *PRICE_COLUMNS, "volume"])
    df["time"] = pd.to_datetime(df["time"], utc=True).astype(TIME_DTYPE)
    return df


def update(granularity: str = "M15", start: str = FIRST_AVAILABLE) -> pd.DataFrame:
    """Download missing candles, save the cache and its manifest, return the full cache."""
    path = dataset_path(granularity)
    step = STEP[granularity]
    cached = pd.read_parquet(path) if path.exists() else None
    if cached is not None and len(cached):
        cached["time"] = cached["time"].astype(TIME_DTYPE)
        frm = cached["time"].iloc[-1] + step
    else:
        frm = pd.Timestamp(start, tz="UTC")
    pages = [] if cached is None else [cached]
    total = 0 if cached is None else len(cached)
    with requests.Session() as session:
        while frm <= pd.Timestamp.now(tz="UTC"):
            page = _fetch_page(session, granularity, frm)
            if cached is not None and len(cached):
                page = page[page["time"] > cached["time"].iloc[-1]]
            if page.empty:
                break
            pages.append(page)
            total += len(page)
            frm = page["time"].iloc[-1] + step
            print(f"\r{total:,} {granularity} candles, up to {frm:%Y-%m-%d %H:%M}", end="", file=sys.stderr)
    print(file=sys.stderr)
    df = pd.concat(pages, ignore_index=True).drop_duplicates("time").sort_values("time", ignore_index=True)
    DATA_DIR.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    write_manifest(granularity, df)
    return df


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(granularity: str, df: pd.DataFrame) -> dict:
    """Record the dataset in data/manifest.json (tracked in git)."""
    path = dataset_path(granularity)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    entry = {
        "file": path.name,
        "provider": "OANDA v20 REST API, /v3/instruments/{instrument}/candles",
        "environment": "live" if os.environ.get("OANDA_ENV") == "live" else "practice",
        "instrument": INSTRUMENT,
        "granularity": granularity,
        "price": "mid, bid and ask OHLC (price=MBA); complete candles only",
        "volume": "OANDA tick volume (price updates), not traded volume",
        "time": "candle open, UTC",
        "rows": len(df),
        "first_open": df["time"].iloc[0].isoformat(),
        "last_open": df["time"].iloc[-1].isoformat(),
        "sha256": file_sha256(path),
        "downloaded_at": pd.Timestamp.now(tz="UTC").floor("s").isoformat(),
    }
    manifest[path.name] = entry
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return entry


def load(granularity: str = "M15", start: str | None = None, end: str | None = None,
         session_only: bool = True) -> pd.DataFrame:
    """Cached candles with time (open, UTC) and close_time; [start, end) on open time.

    session_only drops candles outside TradingView's gold session (the daily
    17:00-18:00 New York break and the weekend), which TradingView never puts
    in a chart candle. Since 2016 these are only 1-2 tick closing prints; before
    2016 OANDA traded through the break, so the session model does not fit
    those years (see results/data_quality/).
    """
    path = dataset_path(granularity)
    if not path.exists():
        raise SystemExit(f"No {granularity} cache yet. Run: python -m gse_research download")
    df = pd.read_parquet(path)
    df["time"] = df["time"].astype(TIME_DTYPE)
    if start:
        df = df[df["time"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df["time"] < pd.Timestamp(end, tz="UTC")]
    if session_only:
        df = df[in_session(df["time"])]
    df = df.reset_index(drop=True)
    df["close_time"] = df["time"] + STEP[granularity]
    return df


def in_session(times: pd.Series) -> pd.Series:
    """True for candles opening inside the gold session: Sunday 18:00 to Friday 17:00 New York, minus the daily break."""
    clock = session_clock(times)
    return (clock.dt.hour < 23) & (clock.dt.dayofweek < 5)


def session_clock(times: pd.Series) -> pd.Series:
    """New York wall time shifted +6h: the 18:00 NY open becomes midnight.

    The clock's date is the trading day (the date of its 17:00 NY close), its
    weekday is Monday-Friday for every trading hour, and hour 23 is the daily
    17:00-18:00 NY break. DST changes happen at weekends, when gold is closed.
    """
    ny = times.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return ny + pd.Timedelta(hours=6)


def aggregate(m15: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Build 1H, 4H, 1D or 1W mid-price candles from M15 with TradingView's session anchors.

    Each candle carries its open time and nominal close time: the last 4H candle
    of a day closes at 17:00 New York (3 hours long); days close at 17:00 New
    York; weeks open Sunday 18:00 and close Friday 17:00 New York. The last row
    can be a candle still in progress if the data ends inside it.
    """
    if tf == "15m":
        return m15.copy()
    t = m15["time"]
    clock = session_clock(t)
    day = clock.dt.floor("D")
    session_end = day + 23 * H  # 17:00 New York
    if tf == "1H":
        start_clock = clock.dt.floor("h")
        end_clock = start_clock + H
    elif tf == "4H":
        start_clock = day + ((clock - day) // (4 * H)) * (4 * H)
        end_clock = (start_clock + 4 * H).where(start_clock + 4 * H <= session_end, session_end)
    elif tf == "1D":
        start_clock = day
        end_clock = session_end
    elif tf == "1W":
        start_clock = day - pd.to_timedelta(day.dt.dayofweek, unit="D")  # clock Monday = Sunday 18:00 NY
        end_clock = start_clock + pd.Timedelta(days=4) + 23 * H  # Friday 17:00 NY
    else:
        raise ValueError(tf)
    # Back to UTC through the candle's own offset: no DST change falls inside a session.
    frame = m15.assign(_start=t - (clock - start_clock), _end=t - (clock - end_clock))
    g = frame.groupby("_start", sort=True)
    out = g.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        close_time=("_end", "first"),
        candles=("open", "size"),
    )
    out["time"] = out.index
    return out.reset_index(drop=True)[["time", "close_time", "open", "high", "low", "close", "volume", "candles"]]


def align(m15: pd.DataFrame, htf: pd.DataFrame, columns: list[str], at: str) -> pd.DataFrame:
    """Higher-timeframe values as GSE's Pine can see them on each M15 candle.

    at="close": the latest HTF candle closed by this M15 candle's close, so an
        HTF candle is visible on the M15 candle that closes with it. This is the
        4H/1H/15m bias readout (`mtf.pine`: the just-closed value, else `[1]`).
    at="open": the latest HTF candle closed by this M15 candle's open, so it
        changes on the first M15 candle of the next period. This is the previous
        day/week/month reference (`engine.pine`: `high[1]` with lookahead on).

    Returns one row per M15 candle (same index) with the HTF `time`, `close_time`
    and `columns`; NaN where no HTF candle has closed yet.
    """
    key = {"close": "close_time", "open": "time"}[at]
    left = pd.DataFrame({"_key": m15[key].astype(TIME_DTYPE), "_row": range(len(m15))})
    right = htf[["time", "close_time", *columns]].rename(columns={"time": "htf_time", "close_time": "htf_close_time"})
    right = right.assign(_key=right["htf_close_time"].astype(TIME_DTYPE)).sort_values("_key")
    merged = pd.merge_asof(left.sort_values("_key"), right, on="_key", direction="backward", allow_exact_matches=True)
    merged = merged.sort_values("_row").drop(columns=["_key", "_row"])
    merged.index = m15.index
    return merged
