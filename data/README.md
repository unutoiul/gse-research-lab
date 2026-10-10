# data

Local market data. The Parquet files are not committed; `manifest.json` is, so every result can name the exact file it used (SHA-256).

```powershell
.venv\Scripts\python -m gse_research download     # fetch or update XAU_USD M15, rewrite manifest.json
.venv\Scripts\python -m gse_research quality      # results/data_quality/XAU_USD_M15.md
```

## Provider

| | |
|---|---|
| Source | OANDA v20 REST API, `GET /v3/instruments/XAU_USD/candles`, `price=MBA` (mid, bid, ask) |
| Environment | `practice` by default (`OANDA_ENV` in `.env`); practice and live serve the same price history |
| Instrument | XAU_USD, OANDA spot gold against the US dollar (an OTC CFD price, not an exchange) |
| History | M15 from 2006-03-19 |
| Candles kept | Complete candles only. OANDA sends no candle for a period without a price update; such gaps stay gaps. Nothing is filled in or fabricated. |

`XAU_USD_M15.parquet` columns: `time` (candle open, UTC), `open high low close` (mid), `bid_open bid_high bid_low bid_close`, `ask_open ask_high ask_low ask_close`, `volume`. Loaders add `close_time` = `time` + 15 minutes.

## Usable period

**2016 onward.** From 2016 every year has no error-level issues, coverage ≥ 0.99 and at most 0.1% thin candles. From 2006 to 2015, OANDA traded through the 17:00–18:00 New York break and at weekend hours, so TradingView's session model does not fit those years. Since 2016, the only candles outside the session are 22 one- or two-tick closing prints, which `data.load()` drops. Details: `results/data_quality/XAU_USD_M15.md`.

## Limitations

- **Not the live GSE feed.** GSE v4.0 runs on TradingView's `BLACKBULL:XAUUSD`, a different liquidity provider with no bulk history available here. An earlier check (not re-verified) found OANDA and BlackBull 15m closes a median 0.12 apart, but a weekly high 4.71 apart. Wick extremes drive pivots and sweeps, so research results will not match BlackBull charts candle for candle (audit B9).
- **Price basis.** Research structure is computed on mid prices. Whether TradingView's BlackBull chart shows bid or mid prices is not established. The Stage 4 parity check compares both against stored TradingView snapshots.
- **Volume is tick volume**: OANDA's count of price updates, not traded volume. It is not comparable with BlackBull's tick volume, and gold has no centralized volume. GSE's volume factor (confluence confirmation) is therefore feed-dependent and is reported with and without volume.
- **Spread.** Bid and ask are known at each candle's open, high, low and close only. Early years have very wide spreads and many single-tick candles; the quality report decides the first usable year.
- **Sessions and holidays.** Higher timeframes use TradingView's anchors for gold. The day runs 18:00 to 17:00 New York with a one-hour break, 4H candles start at 18:00 (the last is 3 hours), and weeks run Sunday 18:00 to Friday 17:00. Holiday early closes are taken from the data; TradingView's holiday calendar is not modelled, so a holiday candle keeps its nominal close time.
- **Timezone.** All stored times are UTC. New York and London times are derived with the IANA time zone database (`tzdata`), so daylight-saving changes are handled per date.

## Using higher timeframes without look-ahead

`gse_research.data.align` places higher-timeframe values on M15 candles exactly as GSE's Pine code can see them:
- `at="close"`: an HTF candle becomes visible on the M15 candle that closes with it. This is the 4H/1H/15m bias readout (`mtf.pine`).
- `at="open"`: it becomes visible on the first M15 candle of the next period. This is the previous day/week/month reference (`engine.pine`, `high[1]` with lookahead on).

Never join on HTF open time.
