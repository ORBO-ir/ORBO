from __future__ import annotations
import pandas as pd
from orbo.clients.history import TSETMCHistoryClient
from orbo.data.transformers import (
    closing_price_to_dataframe,
    today_price_to_dataframe,
    instrument_state_to_dataframe,
)

_PRICE_FIELDS: frozenset[str] = frozenset({
    "pClosing", "pDrCotVal", "priceFirst", "priceMax", "priceMin",
})


class InstrumentHistory:
    def __init__(self, inscode: str | int, count: int = 0) -> None:
        self.inscode = str(inscode)
        self.count   = count
        self._client = TSETMCHistoryClient()

    def fetch(self, count: int | None = None, raw: bool = False, adjust: bool = False) -> pd.DataFrame:
        final_count = self.count if count is None else count
        payload     = self._client.get_daily_history(self.inscode, final_count)
        records     = payload.get("closingPriceDaily", [])
        if adjust and records:
            records = self._apply_adjustment(records)
            payload = {"closingPriceDaily": records}
        return closing_price_to_dataframe(payload, raw=raw)

    def today(self) -> pd.DataFrame:
        payload = self._client.get_today(self.inscode)
        return today_price_to_dataframe(payload)

    def state(self) -> pd.DataFrame:
        records = self._client.get_instrument_state(self.inscode)
        return instrument_state_to_dataframe({"instrumentState": records})

    def _apply_adjustment(self, records: list[dict]) -> list[dict]:
        from orbo.engines.adjustment import AdjustmentEngine
        engine = AdjustmentEngine()
        engine.add_price_adjusts(self._client.get_price_adjusts(self.inscode))
        engine.add_share_changes(self._client.get_share_changes(self.inscode))
        adj_rows = engine.adjust_prices(records, date_field="dEven", price_field="pClosing")
        result: list[dict] = []
        for rec, adj in zip(records, adj_rows):
            adjusted = dict(rec)
            for field in _PRICE_FIELDS:
                if field in adjusted and adjusted[field] is not None:
                    adjusted[field] = adjusted[field] * adj.cum_factor
            result.append(adjusted)
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "InstrumentHistory":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
