from abc import ABC, abstractmethod
import pandas as pd


class BaseEngine(ABC):
    """
    Common contract for all ORBO engines.
    Engines only operate on DataFrames — no network calls, no file I/O.
    """

    @abstractmethod
    def apply(self, data: pd.DataFrame) -> pd.DataFrame: ...
