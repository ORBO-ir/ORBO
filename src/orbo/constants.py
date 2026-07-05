"""Global constants and endpoint URL templates for the ORBO library."""

BASE_URL = "https://cdn.tsetmc.com/api"

DEFAULT_TIMEOUT = 30.0
LOGGER_NAME     = "orbo"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.tsetmc.com/",
    "Origin":  "https://www.tsetmc.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}

MARKETMAP_ALL = (
    "AllAll-TseAll-OtcAll-TseDebt-TseEtf-TseDerivative-"
    "TseStock-OtcDebt-OtcEtf-OtcBase-OtcDerivative-OtcStock-"
)


class Endpoints:
    """
    All TSETMC API endpoint URL templates.

    Usage
    -----
    url = Endpoints.DAILY_HISTORY.format(inscode="123", count=0)
    """

    # ── Daily price data ────────────────────────────────────────────────────
    DAILY_HISTORY   = BASE_URL + "/ClosingPrice/GetClosingPriceDailyList/{inscode}/{count}"
    TODAY_PRICE     = BASE_URL + "/ClosingPrice/GetClosingPriceInfo/{inscode}"
    PRICE_ADJUST    = BASE_URL + "/ClosingPrice/GetPriceAdjustList/{inscode}"

    # ── Intraday historical (requires YYYYMMDD date) ────────────────────────
    TRADES          = BASE_URL + "/Trade/GetTradeHistory/{inscode}/{date}/{combine_same_price}"
    ORDERBOOK       = BASE_URL + "/BestLimits/{inscode}/{date}"
    PRICE_TAPE      = BASE_URL + "/ClosingPrice/GetClosingPriceHistory/{inscode}/{date}"
    SHAREHOLDERS    = BASE_URL + "/Shareholder/{inscode}/{date}"
    CLIENT_TYPE     = BASE_URL + "/ClientType/GetClientTypeHistory/{inscode}/{date}"

    # ── Live / real-time (no date, current session) ─────────────────────────
    LIVE_TRADES          = BASE_URL + "/Trade/GetTrade/{inscode}"
    LIVE_ORDERBOOK       = BASE_URL + "/BestLimits/{inscode}"
    LIVE_CLIENT_TYPE     = BASE_URL + "/ClientType/GetClientType/{inscode}/1/0"

    # ── Instrument metadata ─────────────────────────────────────────────────
    SHARE_CHANGE          = BASE_URL + "/Instrument/GetInstrumentShareChange/{inscode}"
    INSTRUMENT_INFO       = BASE_URL + "/Instrument/GetInstrumentInfo/{inscode}"
    INSTRUMENT_STATE      = BASE_URL + "/MarketData/GetInstrumentStateAll/{inscode}"
    INSTRUMENT_SEARCH     = BASE_URL + "/Instrument/GetInstrumentSearch/{query}"
    INSTRUMENT_MESSAGES   = BASE_URL + "/Msg/GetMsgByInsCode/{inscode}"
    INSTRUMENT_STATISTIC  = BASE_URL + "/MarketData/GetInstrumentStatistic/{inscode}"
    STATIC_THRESHOLD      = BASE_URL + "/MarketData/GetStaticThreshold/{inscode}/{date}"

    # ── Market-wide ─────────────────────────────────────────────────────────
    STATIC_DATA       = BASE_URL + "/StaticData/GetStaticData"
    SERVER_TIME       = BASE_URL + "/StaticData/GetTime"
    MARKET_OVERVIEW   = BASE_URL + "/MarketData/GetMarketOverview/{market_id}"
    RELATED_COMPANIES = BASE_URL + "/ClosingPrice/GetRelatedCompany/{sector_code}"
    TRADE_TOP         = BASE_URL + "/ClosingPrice/GetTradeTop/{board}/{market_id}/{limit}"
    MARKET_MAP        = BASE_URL + "/ClosingPrice/GetMarketMap"

    # ── Options market ───────────────────────────────────────────────────────
    OPTION_CHAIN     = BASE_URL + "/Instrument/GetInstrumentOptionMarketWatch/{market_id}"
    OPTION_CHAIN_CSV = BASE_URL + "/Instrument/GetInstrumentOptionMarketWatchCSV/{market_id}"


    # ── Market indices ────────────────────────────────────────────────────────
    INDEX_SNAPSHOT  = BASE_URL + "/Index/GetIndexB1LastAll/All/{market_id}"
    INDEX_HISTORY   = BASE_URL + "/Index/GetIndexB2History/{ins_code}"
    INDEX_TODAY     = BASE_URL + "/Index/GetIndexB1LastDay/{ins_code}"
    INDEX_COMPANIES = BASE_URL + "/ClosingPrice/GetIndexCompany/{ins_code}"
