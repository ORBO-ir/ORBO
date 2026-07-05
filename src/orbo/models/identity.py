from pydantic import BaseModel, ConfigDict, Field


class InstrumentIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ins_code: str = Field(alias="insCode")
    symbol: str = Field(alias="lVal18AFC")
    name: str = Field(alias="lVal30")
    name_en: str | None = Field(default=None, alias="lVal30En")
    isin: str | None = Field(default=None, alias="cIsin")
    flow: int | None = None
    sector: str | None = Field(default=None, alias="cgrValCot")

    def __repr__(self) -> str:
        return f"InstrumentIdentity(symbol={self.symbol!r}, isin={self.isin!r})"
