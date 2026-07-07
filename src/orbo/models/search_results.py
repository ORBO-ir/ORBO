from __future__ import annotations
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


_ZWNJ = "\u200c"   # Zero Width Non-Joiner — strip from display strings


def _clean(text: str | None) -> str | None:
    """Remove ZWNJ and normalize whitespace for display."""
    if text is None:
        return None
    return re.sub(r"\s+", " ", text.replace(_ZWNJ, "")).strip()


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ins_code:  str       = Field(alias="insCode")
    symbol:    str       = Field(alias="lVal18AFC")
    name:      str       = Field(alias="lVal30")
    flow:      int | None = None
    last_date: int | None = Field(default=None, alias="lastDate")

    @field_validator("symbol", mode="before")
    @classmethod
    def clean_symbol(cls, v: str) -> str:
        return _clean(v) or v

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return _clean(v) or v

    def __repr__(self) -> str:
        return f"SearchResult(symbol={self.symbol!r}, name={self.name!r})"
