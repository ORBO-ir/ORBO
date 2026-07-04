"""
Tests for orbo.engines.trade_side.TradeSideEngine.

All tests use small, hand-crafted DataFrames so expected outputs can be
verified by inspection. No network calls.
"""
import pandas as pd
import pytest
from orbo.engines.trade_side import TradeSideEngine, _tick_rule, _time_str_to_int


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_trades(*price_volume_pairs) -> pd.DataFrame:
    """Build a minimal trades DataFrame from (price, volume) tuples."""
    rows = []
    for i, (price, volume) in enumerate(price_volume_pairs, start=1):
        rows.append({
            "trade_no": i,
            "time":     f"09:{i:02d}:00",
            "price":    float(price),
            "volume":   volume,
            "canceled": 0,
            "date":     "1405-04-07",
        })
    return pd.DataFrame(rows)


def _make_ob_level1(**time_bid_ask_rows) -> pd.DataFrame:
    """
    Build a minimal orderbook DataFrame containing Level-1 rows only.

    Parameters: keyword mapping of time → (bid_price, ask_price).
    Example: _make_ob_level1(**{"09:00:00": (98.0, 102.0)})
    """
    rows = []
    for ref_id, (time, (bid, ask)) in enumerate(time_bid_ask_rows.items(), start=1):
        rows.append({
            "ref_id":    ref_id,
            "time":      time,
            "level":     1,
            "bid_price": float(bid),
            "bid_qty":   1000,
            "bid_orders": 3,
            "ask_price": float(ask),
            "ask_qty":   500,
            "ask_orders": 2,
            "date":      "1405-04-07",
        })
    return pd.DataFrame(rows)


# ── _time_str_to_int ─────────────────────────────────────────────────────────

class TestTimeStrToInt:

    def test_normal_time(self):
        assert _time_str_to_int("09:01:30") == 90130

    def test_midnight(self):
        assert _time_str_to_int("00:00:00") == 0

    def test_end_of_session(self):
        assert _time_str_to_int("12:29:59") == 122959


# ── _tick_rule (standalone function) ────────────────────────────────────────

class TestTickRule:

    def test_single_price_returns_unknown(self):
        sides, methods = _tick_rule([100.0])
        assert sides   == ["unknown"]
        assert methods == ["unknown"]

    def test_ascending_prices_are_buys(self):
        sides, methods = _tick_rule([100.0, 101.0, 102.0])
        assert sides   == ["unknown", "buy", "buy"]
        assert methods == ["unknown", "tick",  "tick"]

    def test_descending_prices_are_sells(self):
        sides, methods = _tick_rule([102.0, 101.0, 100.0])
        assert sides   == ["unknown", "sell", "sell"]
        assert methods == ["unknown", "tick",  "tick"]

    def test_flat_price_after_buy_carries_buy(self):
        sides, methods = _tick_rule([100.0, 102.0, 102.0])
        assert sides   == ["unknown", "buy", "buy"]
        assert methods == ["unknown", "tick", "tick_carry"]

    def test_flat_price_after_sell_carries_sell(self):
        sides, methods = _tick_rule([102.0, 100.0, 100.0])
        assert sides   == ["unknown", "sell", "sell"]
        assert methods == ["unknown", "tick", "tick_carry"]

    def test_flat_price_before_any_direction_stays_unknown(self):
        # first two trades at same price → no direction yet
        sides, methods = _tick_rule([100.0, 100.0, 101.0])
        assert sides   == ["unknown", "unknown", "buy"]
        assert methods == ["unknown", "unknown", "tick"]

    def test_alternating_up_down(self):
        sides, _ = _tick_rule([100.0, 102.0, 98.0, 102.0])
        assert sides == ["unknown", "buy", "sell", "buy"]


# ── TradeSideEngine — Tick Rule only ────────────────────────────────────────

class TestTradeSideEngineTick:

    def test_empty_trades_returns_empty_with_columns(self):
        engine = TradeSideEngine()
        result = engine.classify(pd.DataFrame())
        assert "side"   in result.columns
        assert "method" in result.columns
        assert result.empty

    def test_single_trade_is_unknown(self):
        trades = _make_trades((100, 500))
        result = TradeSideEngine().classify(trades)
        assert result.iloc[0]["side"]   == "unknown"
        assert result.iloc[0]["method"] == "unknown"

    def test_ascending_prices(self):
        trades = _make_trades((100, 500), (102, 300), (104, 200))
        result = TradeSideEngine().classify(trades)
        assert result["side"].tolist()   == ["unknown", "buy", "buy"]
        assert result["method"].tolist() == ["unknown", "tick", "tick"]

    def test_descending_prices(self):
        trades = _make_trades((104, 500), (102, 300), (100, 200))
        result = TradeSideEngine().classify(trades)
        assert result["side"].tolist()   == ["unknown", "sell", "sell"]
        assert result["method"].tolist() == ["unknown", "tick",  "tick"]

    def test_flat_carry_after_uptick(self):
        trades = _make_trades((100, 1000), (102, 500), (102, 400))
        result = TradeSideEngine().classify(trades)
        assert result["side"].tolist()   == ["unknown", "buy", "buy"]
        assert result["method"].tolist() == ["unknown", "tick", "tick_carry"]

    def test_sorted_by_trade_no_regardless_of_input_order(self):
        """Engine must sort by trade_no before classifying."""
        # trade_no=1 → price=102, trade_no=2 → price=100
        trades = _make_trades((102, 500), (100, 300))
        # swap physical row order in the DataFrame
        trades = trades.iloc[::-1].reset_index(drop=True)
        result = TradeSideEngine().classify(trades)
        # after internal sort by trade_no: prices = [102, 100]
        # second trade: 100 < 102 → downtick → sell
        assert result.iloc[0]["side"] == "unknown"
        assert result.iloc[1]["side"] == "sell"
        assert result.iloc[1]["method"] == "tick"

    def test_output_has_all_original_columns(self):
        trades = _make_trades((100, 500), (102, 300))
        result = TradeSideEngine().classify(trades)
        for col in ["trade_no", "time", "price", "volume", "canceled", "date"]:
            assert col in result.columns

    def test_apply_interface_equals_classify(self):
        trades = _make_trades((100, 500), (102, 300))
        engine = TradeSideEngine()
        assert engine.apply(trades).equals(engine.classify(trades))


# ── TradeSideEngine — Quote Rule (with order book) ──────────────────────────

class TestTradeSideEngineQuote:

    def test_trade_at_ask_is_buy(self):
        """Trade price == ask → buyer aggressor (hit the ask)."""
        trades   = _make_trades((102, 500))
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 102.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[0]["side"]   == "buy"
        assert result.iloc[0]["method"] == "quote"

    def test_trade_above_ask_is_buy(self):
        """Trade price > ask → aggressive buy that crossed the spread."""
        trades    = _make_trades((105, 500))
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 102.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[0]["side"]   == "buy"
        assert result.iloc[0]["method"] == "quote"

    def test_trade_at_bid_is_sell(self):
        """Trade price == bid → seller aggressor (hit the bid)."""
        trades    = _make_trades((98, 500))
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 102.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[0]["side"]   == "sell"
        assert result.iloc[0]["method"] == "quote"

    def test_trade_below_bid_is_sell(self):
        trades    = _make_trades((95, 500))
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 102.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[0]["side"]   == "sell"
        assert result.iloc[0]["method"] == "quote"

    def test_trade_between_bid_and_ask_falls_back_to_tick(self):
        """Trade price between bid/ask → ambiguous → use Tick Rule."""
        # Two trades: price goes up → second should be buy/tick
        trades = _make_trades((98, 500), (100, 300))
        # ob: bid=95, ask=105 → price=98 and price=100 are both between
        orderbook = _make_ob_level1(**{"09:00:00": (95.0, 105.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[0]["side"]   == "unknown"  # first trade, no prior
        assert result.iloc[1]["side"]   == "buy"
        assert result.iloc[1]["method"] == "tick"

    def test_no_ask_side_falls_back_to_tick(self):
        """ask_price == 0 means no sellers — cannot apply quote rule."""
        trades    = _make_trades((100, 500), (102, 300))
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 0.0)})  # no ask
        result = TradeSideEngine().classify(trades, orderbook)
        # bid=98, ask=0 → cannot use quote rule for price=100 (not <= bid)
        # → tick rule: second trade at 102 > 100 → buy/tick
        assert result.iloc[1]["side"]   == "buy"
        assert result.iloc[1]["method"] == "tick"

    def test_trade_before_any_ob_update_falls_back_to_tick(self):
        """Trade at 08:59 when ob starts at 09:00 → no ob state yet → tick."""
        trades = pd.DataFrame([{
            "trade_no": 1, "time": "08:59:00", "price": 100.0,
            "volume": 500, "canceled": 0, "date": "1405-04-07",
        }, {
            "trade_no": 2, "time": "09:01:00", "price": 102.0,
            "volume": 300, "canceled": 0, "date": "1405-04-07",
        }])
        orderbook = _make_ob_level1(**{"09:00:00": (98.0, 104.0)})
        result = TradeSideEngine().classify(trades, orderbook)
        # trade 1 at 08:59, ob starts at 09:00 → no match → tick → unknown (first)
        assert result.iloc[0]["side"]   == "unknown"
        # trade 2 at 09:01, ob at 09:00 matches → 98 < 102 < 104 → ambiguous → tick
        # price 102 > 100 → buy/tick
        assert result.iloc[1]["side"]   == "buy"
        assert result.iloc[1]["method"] == "tick"

    def test_empty_orderbook_falls_back_to_tick_rule(self):
        trades    = _make_trades((100, 500), (102, 300))
        orderbook = pd.DataFrame()
        result = TradeSideEngine().classify(trades, orderbook)
        assert result.iloc[1]["side"]   == "buy"
        assert result.iloc[1]["method"] == "tick"


# ── TradeSideEngine — Quote seeds Tick Carry ────────────────────────────────

class TestQuoteSeedsTickCarry:

    def test_tick_carry_seeded_by_prior_quote_classification(self):
        """
        Scenario:
            trade 1: price=98,  ob: bid=99 → sell by QUOTE
            trade 2: price=100, between bid/ask → ambiguous
            trade 3: price=100, same price as trade 2 → tick CARRY from trade 1's sell

        After trade 1 is classified as "sell" by quote rule, the carry
        reference becomes "sell". Trade 2 is ambiguous with a price rise
        (100 > 98), so it becomes "buy/tick" — which resets carry to "buy".
        Trade 3 is flat after trade 2, so carry forward "buy".
        """
        trades = pd.DataFrame([
            {"trade_no": 1, "time": "09:01:00", "price": 98.0,  "volume": 500, "canceled": 0, "date": "1405-04-07"},
            {"trade_no": 2, "time": "09:02:00", "price": 100.0, "volume": 300, "canceled": 0, "date": "1405-04-07"},
            {"trade_no": 3, "time": "09:03:00", "price": 100.0, "volume": 200, "canceled": 0, "date": "1405-04-07"},
        ])
        # ob: bid=99, ask=105 → trade at 98 <= 99 → sell (quote)
        #                     → trade at 100: 99 < 100 < 105 → ambiguous
        orderbook = _make_ob_level1(**{"09:00:00": (99.0, 105.0)})
        result = TradeSideEngine().classify(trades, orderbook)

        assert result.iloc[0]["side"]   == "sell"
        assert result.iloc[0]["method"] == "quote"

        # price 100 > 98 → uptick → buy/tick (resets carry to buy)
        assert result.iloc[1]["side"]   == "buy"
        assert result.iloc[1]["method"] == "tick"

        # same price, carry from buy
        assert result.iloc[2]["side"]   == "buy"
        assert result.iloc[2]["method"] == "tick_carry"
