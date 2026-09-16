from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class NormalizedBatch:
    frame: pl.LazyFrame
    min_business_date: date
    max_business_date: date
    source_type: str


class SourceAdapter(ABC):
    source_type: str
    parser_version: str

    @abstractmethod
    def matches(self, path: Path) -> bool: ...

    @abstractmethod
    def normalize(self, path: Path) -> NormalizedBatch: ...
