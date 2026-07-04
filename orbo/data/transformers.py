"""
Transformation utilities: raw TSETMC API JSON → typed pandas DataFrames.

All public functions accept raw API response dicts and return DataFrames
with Jalali dates, human-readable column names, and derived metrics.
"""
from __future__ import annotations

import pandas as pd
import jdatetime


# ── Column rename map: API field → DataFrame column name ───────────────────
_RENAME_MAP: dict[str, str] = {
    "priceFirst":     "open",
    "priceMax":       "high",
    "priceMin":       "low",
    "pClosing":       "close",
    "pDrCotVal":      "last_price",
    "priceYesterday": "prev_close",
    "zTotTran":       "trade_count",
    "qTotTran5J":     "volume",
    "qTotCap":        "value",
}

# Final column order (matches TSETMC website display)
_DAILY_COLUMNS: list[str] = [
    "date",         # Jalali date  (YYYY-MM-DD)
    "time",         # Last update time (HH:MM:SS) from hEven
    "open",         # priceFirst
    "high",         # priceMax
    "low",          # priceMin
    "close",        # pClosing   — official closing price
    "last_price",   # pDrCotVal  — price of the last executed trade
    "prev_close",   # priceYesterday
    "close_change", # close − prev_close  (calculated)
    "close_pct",    # close_change / prev_close × 100  (calculated)
    "last_change",  # last_price − prev_close  (calculated)
    "last_pct",     # last_change / prev_close × 100  (calculated)
    "trade_count",  # zTotTran
    "volume",       # qTotTran5J
    "value",        # qTotCap  (in Rials)
]

_STATE_COLUMNS: list[str] = [
    "date",
    "time",
    "state_code",   # cEtaval  — e.g. "A ", "I ", "AS"
    "state",        # cEtavalTitle — human-readable Persian label
]

# Fields to extract from GetClosingPriceInfo (today's live response)
_TODAY_FIELDS: frozenset[str] = frozenset({
    "dEven", "hEven",
    "priceFirst", "priceMax", "priceMin",
    "pClosing", "pDrCotVal",
    "priceYesterday",
    "zTotTran", "qTotTran5J", "qTotCap",
})


# ── Private helpers ─────────────────────────────────────────────────────────

def _int_to_jalali(gregorian_int: int) -> str:
    """
    Convert a YYYYMMDD integer to a Jalali date string.

    Parameters
    ----------
    gregorian_int : int
        Gregorian date as YYYYMMDD (e.g. 20260628).

    Returns
    -------
    str
        Jalali date in YYYY-MM-DD format (e.g. "1405-04-07").

    Example
    -------
    >>> _int_to_jalali(20260628)
    '1405-04-07'
    """
    g = pd.Timestamp(str(gregorian_int))
    return jdatetime.date.fromgregorian(date=g.date()).strftime("%Y-%m-%d")


def _int_to_time(heven: int) -> str:
    """
    Convert a HHMMSS integer to a time string.

    Parameters
    ----------
    heven : int
        Time encoded as HHMMSS (e.g. 122959).

    Returns
    -------
    str
        Time in HH:MM:SS format (e.g. "12:29:59").

    Example
    -------
    >>> _int_to_time(122959)
    '12:29:59'
    """
    h = heven // 10000
    m = (heven % 10000) // 100
    s = heven % 100
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_daily_df(records: list[dict]) -> pd.DataFrame:
    """
    Shared pipeline for both historical and today's data.

    Steps
    -----
    1. Sort ascending by original Gregorian date (dEven integer).
    2. Convert date and time fields.
    3. Rename API columns to human-readable names.
    4. Compute derived change and percentage columns.
    5. Select and order final columns.
    """
    df = pd.DataFrame(records)

    # 1. Sort by raw Gregorian date before any conversion
    df = df.sort_values("dEven").reset_index(drop=True)

    # 2. Date and time
    df["date"] = df["dEven"].apply(_int_to_jalali)
    df["time"] = df["hEven"].apply(_int_to_time)

    # 3. Rename
    df = df.rename(columns=_RENAME_MAP)

    # 4. Derived columns — always calculated from actual prices
    df["close_change"] = df["close"]      - df["prev_close"]
    df["last_change"]  = df["last_price"] - df["prev_close"]
    df["close_pct"]    = (df["close_change"] / df["prev_close"] * 100).round(2)
    df["last_pct"]     = (df["last_change"]  / df["prev_close"] * 100).round(2)

    # 5. Final column selection
    existing = [c for c in _DAILY_COLUMNS if c in df.columns]
    return df[existing]


# ── Public transformers ─────────────────────────────────────────────────────

def closing_price_to_dataframe(
    payload: dict,
    raw: bool = False,
) -> pd.DataFrame:
    """
    Convert a GetClosingPriceDailyList API response to a DataFrame.

    Parameters
    ----------
    payload : dict
        Raw JSON response from the TSETMC API.
    raw : bool
        If True, return the unmodified DataFrame with original API column
        names and no derived columns. Useful for debugging or feeding
        directly into AdjustmentEngine.

    Returns
    -------
    pd.DataFrame
        Sorted ascending by date. Empty DataFrame if no records found.

    Columns (when raw=False)
    ------------------------
    date, time, open, high, low, close, last_price, prev_close,
    close_change, close_pct, last_change, last_pct,
    trade_count, volume, value

    Example
    -------
    >>> raw_data = client.get_daily_history("35700344742885862")
    >>> df = closing_price_to_dataframe(raw_data)
    >>> df[["date", "close", "volume"]].head()
    """
    records = payload.get("closingPriceDaily", [])

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if raw:
        return df.sort_values("dEven").reset_index(drop=True)

    return _build_daily_df(records)


def today_price_to_dataframe(payload: dict) -> pd.DataFrame:
    """
    Convert a GetClosingPriceInfo API response to a single-row DataFrame.

    The output schema is identical to closing_price_to_dataframe so that
    today's row can be appended to the historical DataFrame without
    any further transformation.

    Parameters
    ----------
    payload : dict
        Raw JSON response from GetClosingPriceInfo endpoint.

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame. Empty if the response is missing or malformed.

    Note
    ----
    The API returns ``priceChange: 0`` during live sessions because the
    field is only populated after market close. This transformer always
    recomputes change columns from actual price fields, so live data
    is correct regardless.
    """
    info = payload.get("closingPriceInfo", {})

    if not info:
        return pd.DataFrame()

    # Extract only the OHLCV-compatible fields; discard nested objects
    record = {k: v for k, v in info.items() if k in _TODAY_FIELDS}

    return _build_daily_df([record])


def instrument_state_to_dataframe(payload: dict) -> pd.DataFrame:
    """
    Convert a GetInstrumentStateAll API response to a DataFrame.

    Parameters
    ----------
    payload : dict
        Raw JSON response from GetInstrumentStateAll endpoint.

    Returns
    -------
    pd.DataFrame
        Columns: date, time, state_code, state.
        Sorted ascending by date then time.

    State codes
    -----------
    "A " → Allowed (مجاز)
    "I " → Forbidden (ممنوع)
    "AR" → Allowed-Reserved (مجاز-محفوظ)
    "IR" → Forbidden-Reserved (ممنوع-محفوظ)
    "AS" → Allowed-Halted (مجاز-متوقف)
    "IS" → Forbidden-Halted (ممنوع-متوقف)
    """
    records = payload.get("instrumentState", [])

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = df["dEven"].apply(_int_to_jalali)
    df["time"] = df["hEven"].apply(_int_to_time)

    df = df.rename(columns={
        "cEtaval":      "state_code",
        "cEtavalTitle": "state",
    })

    existing = [c for c in _STATE_COLUMNS if c in df.columns]
    return (
        df[existing]
        .sort_values(["date", "time"])
        .reset_index(drop=True)
    )



    
# ═══════════════════════════════════════════════════════════════════════════
# Intraday transformers
# ═══════════════════════════════════════════════════════════════════════════

def trade_history_to_dataframe(records: list[dict], date: str) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df = df.sort_values("nTran").reset_index(drop=True)
    df["date"] = _int_to_jalali(int(date))
    df["time"] = df["hEven"].apply(_int_to_time)
    df = df.rename(columns={"nTran": "trade_no", "pTran": "price", "qTitTran": "volume"})
    return df[["date", "time", "trade_no", "price", "volume", "canceled"]]


def orderbook_to_dataframe(records: list[dict], date: str) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df = df.sort_values("refID").reset_index(drop=True)
    df["date"] = _int_to_jalali(int(date))
    df["time"] = df["hEven"].apply(_int_to_time)
    df = df.rename(columns={
        "refID": "ref_id", "number": "level",
        "pMeDem": "bid_price", "qTitMeDem": "bid_qty", "zOrdMeDem": "bid_orders",
        "pMeOf": "ask_price", "qTitMeOf": "ask_qty", "zOrdMeOf": "ask_orders",
    })
    return df[["date", "time", "ref_id", "level",
               "bid_price", "bid_qty", "bid_orders",
               "ask_price", "ask_qty", "ask_orders"]]


def price_tape_to_dataframe(records: list[dict], date: str) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df = df.sort_values("hEven").reset_index(drop=True)
    df["date"] = _int_to_jalali(int(date))
    df["time"] = df["hEven"].apply(_int_to_time)
    df = df.rename(columns=_RENAME_MAP)
    cols = ["date", "time", "close", "last_price", "trade_count", "volume", "value"]
    return df[[c for c in cols if c in df.columns]]


def shareholders_to_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["date"] = df["dEven"].apply(_int_to_jalali)
    df = df.rename(columns={
        "shareHolderName": "shareholder", "cIsin": "isin",
        "numberOfShares": "shares", "perOfShares": "percent",
        "change": "change_code", "changeAmount": "change_amount",
    })
    cols = ["date", "shareholder", "isin", "shares", "percent", "change_code", "change_amount"]
    return (df[[c for c in cols if c in df.columns]]
            .sort_values(["date", "shares"], ascending=[True, False])
            .reset_index(drop=True))


def client_type_to_dataframe(record: dict, date: str) -> pd.DataFrame:
    if not record:
        return pd.DataFrame()
    row = {
        "date":              _int_to_jalali(int(date)),
        "real_buy_volume":   record.get("buy_I_Volume"),
        "legal_buy_volume":  record.get("buy_N_Volume"),
        "real_buy_value":    record.get("buy_I_Value"),
        "legal_buy_value":   record.get("buy_N_Value"),
        "real_buy_count":    record.get("buy_I_Count"),
        "legal_buy_count":   record.get("buy_N_Count"),
        "real_sell_volume":  record.get("sell_I_Volume"),
        "legal_sell_volume": record.get("sell_N_Volume"),
        "real_sell_value":   record.get("sell_I_Value"),
        "legal_sell_value":  record.get("sell_N_Value"),
        "real_sell_count":   record.get("sell_I_Count"),
        "legal_sell_count":  record.get("sell_N_Count"),
    }
    row["net_real_volume"] = row["real_buy_volume"] - row["real_sell_volume"]
    row["net_real_value"]  = row["real_buy_value"]  - row["real_sell_value"]
    return pd.DataFrame([row])


# ═══════════════════════════════════════════════════════════════════════════
# Live data transformers
# ═══════════════════════════════════════════════════════════════════════════

def live_orderbook_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert a live BestLimits snapshot to a 5-level order-book DataFrame.

    Unlike the historical order-book transformer (which processes an
    incremental update stream and requires a date), this transformer
    receives a complete 5-level snapshot from the live endpoint and
    returns it directly.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCLiveClient.get_live_orderbook(). Always
        contains exactly 5 rows (one per depth level).

    Returns
    -------
    pd.DataFrame
        Columns: level, bid_price, bid_qty, bid_orders,
                 ask_price, ask_qty, ask_orders.
        Sorted ascending by level (1 = best price).
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values("number").reset_index(drop=True)
    df = df.rename(columns={
        "number":    "level",
        "pMeDem":    "bid_price",
        "qTitMeDem": "bid_qty",
        "zOrdMeDem": "bid_orders",
        "pMeOf":     "ask_price",
        "qTitMeOf":  "ask_qty",
        "zOrdMeOf":  "ask_orders",
    })
    return df[["level", "bid_price", "bid_qty", "bid_orders",
               "ask_price", "ask_qty", "ask_orders"]]


def live_client_type_to_dataframe(record: dict, date: str | None = None) -> pd.DataFrame:
    """
    Convert a live GetClientType response to a single-row DataFrame.

    The live client-type endpoint uses slightly different field names
    from the historical version (CountI/CountN vs I_Count/N_Count) and
    omits per-side value fields. Two derived columns are added:
    net_real_volume and net_real_value (if value data is absent,
    net_real_value is NaN).

    Parameters
    ----------
    record : dict
        Raw record from TSETMCLiveClient.get_live_client_type().
    date : str | None
        Optional YYYYMMDD date string. If None, no date column is added.

    Returns
    -------
    pd.DataFrame
        Single row.
    """
    if not record:
        return pd.DataFrame()

    row: dict = {}
    if date is not None:
        row["date"] = _int_to_jalali(int(date))

    # Live endpoint uses CountI/CountN naming (not I_Count/N_Count)
    row["real_buy_volume"]  = record.get("buy_I_Volume")
    row["legal_buy_volume"] = record.get("buy_N_Volume")
    row["real_buy_count"]   = record.get("buy_CountI")
    row["legal_buy_count"]  = record.get("buy_CountN")
    row["real_sell_volume"] = record.get("sell_I_Volume")
    row["legal_sell_volume"]= record.get("sell_N_Volume")
    row["real_sell_count"]  = record.get("sell_CountI")
    row["legal_sell_count"] = record.get("sell_CountN")

    buy_vol  = row.get("real_buy_volume")  or 0
    sell_vol = row.get("real_sell_volume") or 0
    row["net_real_volume"] = buy_vol - sell_vol

    return pd.DataFrame([row])


# ═══════════════════════════════════════════════════════════════════════════
# Option chain transformer
# ═══════════════════════════════════════════════════════════════════════════

# JSON field → clean DataFrame column
_OPTION_RENAME: dict[str, str] = {
    # Call side
    "lVal18AFC_C":   "call_symbol",
    "zTotTran_C":    "call_trades",
    "qTotTran5J_C":  "call_volume",
    "qTotCap_C":     "call_value",
    "notionalValue_C": "call_notional",
    "oP_C":          "call_oi",
    "pClosing_C":    "call_close",
    "pDrCotVal_C":   "call_last",
    "pMeDem_C":      "call_bid",
    "qTitMeDem_C":   "call_bid_size",
    "pMeOf_C":       "call_ask",
    "qTitMeOf_C":    "call_ask_size",
    # Put side
    "lVal18AFC_P":   "put_symbol",
    "zTotTran_P":    "put_trades",
    "qTotTran5J_P":  "put_volume",
    "qTotCap_P":     "put_value",
    "notionalValue_P": "put_notional",
    "oP_P":          "put_oi",
    "pClosing_P":    "put_close",
    "pDrCotVal_P":   "put_last",
    "pMeDem_P":      "put_bid",
    "qTitMeDem_P":   "put_bid_size",
    "pMeOf_P":       "put_ask",
    "qTitMeOf_P":    "put_ask_size",
    # Shared
    "strikePrice":       "strike",
    "remainedDay":       "dte",
    "contractSize":      "contract_size",
    "lval30_UA":         "underlying_symbol",
    "pClosing_UA":       "underlying_close",
    "pDrCotVal_UA":      "underlying_last",
    "priceYesterday_UA": "underlying_prev_close",
    "beginDate":         "listing_date",
    "endDate":           "expiry_gregorian",
}

_OPTION_COLUMNS_ORDERED: list[str] = [
    "underlying_symbol",
    "strike", "dte", "contract_size",
    "expiry_jalali", "expiry_gregorian", "listing_date",
    "underlying_close", "underlying_last", "underlying_prev_close",
    # Call
    "call_symbol", "call_moneyness",
    "call_close", "call_last", "call_bid", "call_ask",
    "call_bid_size", "call_ask_size",
    "call_volume", "call_trades", "call_value", "call_notional", "call_oi",
    # Put
    "put_symbol", "put_moneyness",
    "put_close", "put_last", "put_bid", "put_ask",
    "put_bid_size", "put_ask_size",
    "put_volume", "put_trades", "put_value", "put_notional", "put_oi",
]


def _option_moneyness(strike: float, underlying: float, opt_type: str) -> str:
    """
    Classify moneyness: ITM / ATM / OTM.

    Call: ITM if S > K, OTM if S < K
    Put:  ITM if S < K, OTM if S > K
    """
    if abs(strike - underlying) < 0.01:
        return "ATM"
    if opt_type == "call":
        return "ITM" if underlying > strike else "OTM"
    else:
        return "ITM" if underlying < strike else "OTM"


def option_chain_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert raw GetInstrumentOptionMarketWatch records to a tidy DataFrame.

    Each record represents one call/put pair at one strike price.
    The output has one row per strike, with both call and put columns
    side-by-side — matching the standard option chain table layout.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCOptionClient.get_chain().

    Returns
    -------
    pd.DataFrame
        Columns: underlying_symbol, strike, dte, contract_size,
        expiry_jalali, expiry_gregorian, underlying_close/last/prev_close,
        call_symbol, call_moneyness, call_close/last/bid/ask/...,
        put_symbol, put_moneyness, put_close/last/bid/ask/...

        Sorted ascending by underlying_symbol, then expiry, then strike.

    Note on moneyness
    -----------------
    Moneyness is computed from underlying_close (official closing price).
    During live sessions this may lag the actual last trade price.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.rename(columns=_OPTION_RENAME)

    # ── Jalali expiry ────────────────────────────────────────────────────
    df["expiry_jalali"] = df["expiry_gregorian"].apply(
        lambda d: _int_to_jalali(int(d)) if pd.notna(d) else None
    )

    # ── Moneyness ────────────────────────────────────────────────────────
    df["call_moneyness"] = df.apply(
        lambda r: _option_moneyness(r["strike"], r["underlying_close"], "call"),
        axis=1,
    )
    df["put_moneyness"] = df.apply(
        lambda r: _option_moneyness(r["strike"], r["underlying_close"], "put"),
        axis=1,
    )

    # ── Select and order columns ─────────────────────────────────────────
    cols = [c for c in _OPTION_COLUMNS_ORDERED if c in df.columns]
    df = df[cols]

    return (
        df.sort_values(
            ["underlying_symbol", "expiry_jalali", "strike"],
            ascending=True,
        )
        .reset_index(drop=True)
    )


# ═══════════════════════════════════════════════════════════════════════════
# Market index transformers
# ═══════════════════════════════════════════════════════════════════════════

def index_snapshot_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert GetIndexB1LastAll records to a tidy snapshot DataFrame.

    Each row is one market index showing its current value, daily
    high/low, absolute change, and percentage change.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCIndexClient.get_snapshot().

    Returns
    -------
    pd.DataFrame
        Columns: ins_code, name, time, value, high, low,
                 change, change_pct.
        change_pct is already in percent (e.g. 1.78 means +1.78%).
        Sorted by name ascending.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["time"] = df["hEven"].apply(_int_to_time)

    df = df.rename(columns={
        "insCode":        "ins_code",
        "lVal30":         "name",
        "xDrNivJIdx004":  "value",
        "xPhNivJIdx004":  "high",
        "xPbNivJIdx004":  "low",
        "xVarIdxJRfV":    "change_pct",   # already in %, e.g. 1.7779 = +1.78%
        "indexChange":    "change",
    })

    cols = ["ins_code", "name", "time", "value", "high", "low", "change", "change_pct"]
    existing = [c for c in cols if c in df.columns]
    return df[existing].sort_values("name").reset_index(drop=True)


def index_history_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert GetIndexB2History records to a tidy historical DataFrame.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCIndexClient.get_history().

    Returns
    -------
    pd.DataFrame
        Columns: date (Jalali YYYY-MM-DD), value, low, high.
        Sorted ascending by date (oldest first).
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = df["dEven"].apply(_int_to_jalali)

    df = df.rename(columns={
        "xNivInuClMresIbs": "value",
        "xNivInuPbMresIbs": "low",
        "xNivInuPhMresIbs": "high",
    })

    return (
        df[["date", "value", "low", "high"]]
        .sort_values("date")
        .reset_index(drop=True)
    )


def index_today_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert GetIndexB1LastDay records to an intraday time-series DataFrame.

    Records are published at fixed intervals (~25 min) during the session.
    The high and low fields reflect the running intraday extremes up to
    each point in time.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCIndexClient.get_today().

    Returns
    -------
    pd.DataFrame
        Columns: time, value, high, low, change_pct.
        Sorted ascending by time.

    Note
    ----
    The first few rows of each session (before market open) have
    high=0 and low=0 because no intraday extremes have been established yet.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["time"] = df["hEven"].apply(_int_to_time)

    df = df.rename(columns={
        "xDrNivJIdx004": "value",
        "xPhNivJIdx004": "high",
        "xPbNivJIdx004": "low",
        "xVarIdxJRfV":   "change_pct",
    })

    cols = ["time", "value", "high", "low", "change_pct"]
    existing = [c for c in cols if c in df.columns]
    return df[existing].sort_values("time").reset_index(drop=True)


def index_companies_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert GetIndexCompany records to a constituent-companies DataFrame.

    Each row is one company that belongs to the requested index, showing
    live price data alongside the company identity.

    Parameters
    ----------
    records : list[dict]
        Raw records from TSETMCIndexClient.get_companies().

    Returns
    -------
    pd.DataFrame
        Columns: ins_code, symbol, name, close, last_price, prev_close,
                 change, low, high, trade_count, volume, value.
        Sorted alphabetically by symbol.
    """
    if not records:
        return pd.DataFrame()

    rows = []
    for r in records:
        instrument = r.get("instrument") or {}
        rows.append({
            "ins_code":   instrument.get("insCode"),
            "symbol":     instrument.get("lVal18AFC"),
            "name":       instrument.get("lVal30"),
            "close":      r.get("pClosing"),
            "last_price": r.get("pDrCotVal"),
            "prev_close": r.get("priceYesterday"),
            "change":     r.get("priceChange"),
            "low":        r.get("priceMin"),
            "high":       r.get("priceMax"),
            "trade_count": r.get("zTotTran"),
            "volume":     r.get("qTotTran5J"),
            "value":      r.get("qTotCap"),
        })

    return (
        pd.DataFrame(rows)
        .sort_values("symbol")
        .reset_index(drop=True)
    )
