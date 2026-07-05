from pydantic import BaseModel, ConfigDict, Field


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ins_code: str = Field(alias="insCode")
    symbol: str = Field(alias="lVal18AFC")
    name: str = Field(alias="lVal30")
    flow: int | None = None
    last_date: int | None = Field(default=None, alias="lastDate")

    def __repr__(self) -> str:
        return f"SearchResult(symbol={self.symbol!r}, name={self.name!r})"
