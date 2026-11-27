# Class 3 lab data: hourly prices

Data for the Class 3 coding lab, *`PriceAmericanPut` on market data*. The tasks
are on the lab slides of the Class 3 deck.

## Files

`hourly/<SYMBOL>.csv`, one file per asset, 1 November 2021 00:00 UTC to
31 October 2026 23:00 UTC (five years, 43,824 hours):

```text
timestamp_utc,close
2021-11-01T00:00:00Z,61560.49
```

- `timestamp_utc`: start of the hour, in Coordinated Universal Time (UTC).
- `close`: last trade price in that hour, in Tether (USDT), a stablecoin that
  tracks the US dollar.
- Hours in which the exchange did not trade are missing, not filled. Count rows;
  do not assume exactly 8,760 rows per year.

| Asset | File |
|---|---|
| Bitcoin | `hourly/BTCUSDT.csv` |
| Gold: Pax Gold, one token per fine troy ounce | `hourly/PAXGUSDT.csv` |
| 38 further cryptocurrencies | the other files in `hourly/` |
| S&P 500 index | run `python3 Class3/data/fetch_sp500.py` (see below) |

## S&P 500

S&P 500 levels are licensed by S&P Dow Jones Indices, so they are not stored
here. From the repository root, run once:

```bash
python3 Class3/data/fetch_sp500.py
```

This writes `hourly/SP500.csv` in the same format from Yahoo Finance, for your
own use. It covers about the last three years of New York trading hours (about
seven bars per trading day). The file is ignored by git: do not commit it.

## Source

Binance public market data, spot klines with a one-hour interval:
<https://data.binance.vision/?prefix=data/spot/monthly/klines/>.
`build_hourly_data.py` rebuilds every file (standard library only; it downloads
about 2,400 archives). You do not need to run it.

Do not edit these files. Put your own code and results in
`Submissions/LastnameFirstname/Class3/`.
