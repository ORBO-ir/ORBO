# orbo

**Tehran Stock Exchange data, done right.**

[فارسی](README.fa.md) &nbsp;·&nbsp;
[![PyPI](https://img.shields.io/pypi/v/orbo)](https://pypi.org/project/orbo/)
[![Python](https://img.shields.io/pypi/pyversions/orbo)](https://pypi.org/project/orbo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

`orbo` is a Python SDK for [TSETMC](https://www.tsetmc.com).
It turns raw API responses into clean, Jalali-dated DataFrames — with price adjustment,
order-flow classification, and live data built in.

```python
import orbo

stock = orbo.Instrument("شپنا")

# Adjusted daily history — Jalali dates, derived returns
df = stock.history(adjust=True)
#         date      open    high     low   close  volume
# 0  1394-01-05  7,230.0  7,420.0  7,210.0  7,380.0  3.2M
# …
# 1403-11-22   41,250.0  42,100.0  41,100.0  41,900.0  8.7M

# Return distribution
stats = stock.stats()
print(stats.descriptive["std"])         # daily return std
print(stats.distribution["tail_type"])  # fat_tail / thin_tail / normal_tail

# Intraday order flow
session    = stock.intraday("20260628")
classified = orbo.TradeSideEngine().classify(session.trades, session.orderbook)
result     = orbo.FootprintEngine().build(classified)
print(result.poc_price)    # Point of Control — highest-volume price
print(result.total_delta)  # net buy pressure for the session
```

---

## Install

```bash
pip install orbo
```

Requires Python ≥ 3.11. Works from inside Iran without VPN.

---

## What it does

| | |
|---|---|
| `stock.history(adjust=True)` | Full OHLCV history, price-adjusted for dividends and capital increases |
| `stock.today()` | Live current-session price |
| `stock.stats()` | Daily/monthly/yearly returns, skewness, kurtosis, tail type |
| `stock.intraday(date)` | Trades, order book, price tape, shareholders, client-type flows |
| `stock.live()` | Live price + trades + 5-level book + real/legal flows in one call |
| `TradeSideEngine` | Lee-Ready aggressor classification (Quote Rule + Tick Rule) |
| `FootprintEngine` | Per-price buy/sell volume, delta, POC, imbalance flags |
| `OptionChain.fetch()` | Full listed option chain with moneyness — refreshable live |
| `find_index("شاخص كل")` | TSE/OTC indices — history, intraday, constituent companies |

---

## Examples

### Price history and statistics

```python
stock = orbo.Instrument("فملی")
df    = stock.history(adjust=True, count=252)   # last year, adjusted

stats = stock.stats(adjust=True)
print(stats.descriptive)   # mean, median, std, min, max, range
print(stats.monthly)       # compounded monthly returns table
print(stats.distribution)  # skewness, kurtosis, fat-tail classification
```

### Intraday order flow → footprint

```python
session = orbo.Instrument("شپنا").intraday("20260628")

# Classify each trade as aggressive buy or sell (Lee-Ready algorithm)
classified = orbo.TradeSideEngine().classify(
    session.trades,
    session.orderbook,   # enables Quote Rule; falls back to Tick Rule
)

# Aggregate into per-price footprint bars
fp = orbo.FootprintEngine().build(classified)
print(fp.bars[["price","buy_volume","sell_volume","delta","imbalance"]])
print(fp.summary())
```

### Option chain

```python
chain = orbo.OptionChain.fetch()             # full snapshot, all markets
chain.refresh()                              # update prices in-place

print(chain.underlyings)                     # ["اهرم", "توان", ...]
df = chain.for_expiry("اهرم", "1405-05-31") # one strike table
print(chain.summary())                       # n_strikes + OI per expiry
```

### Market indices

```python
idx = orbo.find_index("شاخص كل")    # search by name
df  = idx.history()                  # full daily values, Jalali dates

stats = idx.stats()
print(stats.yearly)
```

### Batch intraday with automatic retry

```python
sessions, failed = orbo.fetch_intraday_range(
    inscode = "7745894403636165",
    dates   = ["20260622", "20260623", "20260624", "20260625"],
    fields  = ["trades", "orderbook"],
)
# failed → dates that didn't come through after all retry rounds
```

---

## Architecture

```
orbo/
├── clients/        httpx wrappers — retry on every call
├── data/           transformers — JSON → typed DataFrames, Jalali dates
├── engines/        pure computation — no network, fully testable
│   ├── adjustment  backward cumulative price adjustment
│   ├── trade_side  Lee-Ready aggressor classification
│   ├── footprint   per-price order-flow aggregation
│   ├── daily_stats return series + distribution stats
│   └── intra_stats VWAP + tick-level distribution
├── registry/       local Parquet cache for symbol → inscode lookup
└── instrument.py   unified high-level entry point
```

Engines never touch the network.
Transformers own all renaming and date conversion.
Clients retry automatically (3 attempts, exponential backoff).

---

## Coming next — `orbo-quant`

A separate library that reads from `orbo` and adds options analytics:
Black-Scholes pricing, Greeks (Δ Γ Θ ν ρ), implied volatility, IV surface,
strategy builder, and portfolio optimization.

`orbo` stays focused on data. Analytics live in `orbo-quant`.

---

## Development

```bash
git clone https://github.com/ORBO-ir/ORBO.git
cd ORBO
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT © 2026 — [ORBO-ir](https://github.com/ORBO-ir)
