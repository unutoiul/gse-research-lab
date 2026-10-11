# GSE research

Reproducible research and backtesting for Gold Structure Engine (GSE) v4.0 on XAU/USD. It tests one structure rule at a time against a documented baseline. The live TradingView indicator lives in the `gse-website` repository and is never changed from here.

Start with [GSE_BASELINE_AUDIT.md](GSE_BASELINE_AUDIT.md) (what GSE v4.0 actually does) and [R001_PLAN.md](R001_PLAN.md) (the first experiment).

## Layout

| Path | Contents |
|---|---|
| `gse_research/` | Python package: data pipeline now; structure, signals, backtest, metrics and experiments as they are built |
| `data/` | Local market data (not committed), with its provider notes and manifest |
| `config/` | Versioned experiment settings |
| `results/` | Reports, trade logs and data-quality reports |
| `tests/` | Unit, regression and anti-look-ahead tests |

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Put the OANDA credentials in `.env` (never committed):

```
OANDA_API_TOKEN=...
OANDA_ENV=practice
```

## Commands

```powershell
.venv\Scripts\python -m gse_research download   # OANDA XAU_USD M15 to data/, see data/README.md
.venv\Scripts\python -m gse_research quality    # data-quality report to results/data_quality/
.venv\Scripts\python -m gse_research r001 --period train   # R001 experiment to results/R001/<period>/
.venv\Scripts\python -m gse_research optimize  # study O1: settings search, results/O1/ (about 15 minutes)
.venv\Scripts\python -m pytest
```
