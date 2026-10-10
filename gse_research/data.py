"""OANDA XAU_USD candle cache and TradingView-style higher timeframes.

Candles are stored in data/XAU_USD_M15.parquet (git-ignored); later runs only
download what is missing. Prices are OANDA mid prices; `spread` is ask minus bid
at the candle close, used for trading costs.

Higher timeframes are built from M15 the way TradingView builds them for gold:
the trading day opens at 18:00 New York (22:00 UTC in summer, 23:00 in winter)
and closes at 17:00 New York. 4H candles start at the day's open, so the last
one is cut to 3 hours. 1H candles run on the clock hour.
"""

from __future__ import annotations

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
M15_FILE = DATA_DIR / f"{INSTRUMENT}_M15.parquet"
M15 = pd.Timedelta(minutes=15)
FIRST_AVAILABLE = "2006-01-01"  # OANDA's gold M15 history starts 2006-03-19

load_dotenv(ROOT / ".env")


def _host() -> str:
    live = os.environ.get("OANDA_ENV") == "live"
    return "https://api-fxtrade.oanda.com" if live else "https://api-fxpractice.oanda.com"


def _fetch_page(session: requests.Session, start: pd.Timestamp) -> pd.DataFrame:
    token = os.environ.get("OANDA_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("OANDA_API_TOKEN is not set in .env")
    params = {
        "granularity": "M15",
        "price": "MBA",
        "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": 5000,
    }
    url = f"{_host()}/v3/instruments/{INSTRUMENT}/candles"
    for attempt in range(5):
        res = session.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
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
            float(c["mid"]["o"]),
            float(c["mid"]["h"]),
            float(c["mid"]["l"]),
            float(c["mid"]["c"]),
            float(c["bid"]["c"]),
            float(c["ask"]["c"]),
            int(c["volume"]),
        )
        for c in res.json()["candles"]
        if c["complete"]
    ]
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "bid", "ask", "volume"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def update(start: str = FIRST_AVAILABLE) -> pd.DataFrame:
    """Download missing M15 candles and return the full cache."""
    cached = pd.read_parquet(M15_FILE) if M15_FILE.exists() else None
    frm = cached["time"].iloc[-1] + M15 if cached is not None and len(cached) else pd.Timestamp(start, tz="UTC")
    pages = [] if cached is None else [cached[["time", "open", "high", "low", "close", "bid", "ask", "volume"]]]
    total = 0 if cached is None else len(cached)
    with requests.Session() as session:
        while True:
            page = _fetch_page(session, frm)
            if cached is not None:
                page = page[page["time"] > cached["time"].iloc[-1]]
            if page.empty:
                break
            pages.append(page)
            total += len(page)
            frm = page["time"].iloc[-1] + M15
            print(f"\r{total:,} candles, up to {frm:%Y-%m-%d %H:%M}", end="", file=sys.stderr)
            if frm > pd.Timestamp.now(tz="UTC"):
                break
    print(file=sys.stderr)
    df = pd.concat(pages, ignore_index=True).drop_duplicates("time").sort_values("time", ignore_index=True)
    df["spread"] = (df["ask"] - df["bid"]).round(3)
    DATA_DIR.mkdir(exist_ok=True)
    df.to_parquet(M15_FILE, index=False)
    return df


def load_m15(start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Cached M15 candles: time (open, UTC), close_time, OHLC, volume, spread."""
    if not M15_FILE.exists():
        raise SystemExit("No candle cache yet. Run: python -m gse_research download")
    df = pd.read_parquet(M15_FILE)
    if start:
        df = df[df["time"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df["time"] < pd.Timestamp(end, tz="UTC")]
    df = df.reset_index(drop=True)
    df["close_time"] = df["time"] + M15
    return df


def _session_clock(times: pd.Series) -> pd.Series:
    """New York wall time shifted +6h, so the 18:00 NY open becomes midnight."""
    ny = times.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return ny + pd.Timedelta(hours=6)


def aggregate(m15: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Build 1H, 4H, 1D or 1W candles from M15 with TradingView's session rules.

    Each candle carries its TradingView open time and close time; the last 4H
    candle of a day closes at 17:00 New York, so it is 3 hours long.
    """
    if tf == "15m":
        return m15.copy()
    H = pd.Timedelta(hours=1)
    t = m15["time"]
    clock = _session_clock(t)
    day = clock.dt.floor("D")
    session_end = day + 23 * H  # 17:00 New York
    if tf == "1H":
        start = t.dt.floor("h")
        end = start + H
    elif tf == "4H":
        start_clock = day + ((clock - day) // (4 * H)) * (4 * H)
        end_clock = (start_clock + 4 * H).where(start_clock + 4 * H <= session_end, session_end)
        start = t - (clock - start_clock)
        end = t - (clock - end_clock)
    elif tf == "1D":
        start = t - (clock - day)
        end = t - (clock - session_end)
    elif tf == "1W":
        # Weeks open Sunday 18:00 New York (Monday 00:00 on the shifted clock).
        monday = day - pd.to_timedelta(day.dt.dayofweek, unit="D")
        start = t - (clock - monday)
        end = None
    else:
        raise ValueError(tf)
    frame = m15.assign(_start=start)
    g = frame.groupby("_start", sort=True)
    out = g.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    out["time"] = out.index
    out["close_time"] = g["time"].last() + M15 if end is None else frame.assign(_end=end).groupby("_start")["_end"].first()
    return out.reset_index(drop=True)[["time", "close_time", "open", "high", "low", "close", "volume"]]
