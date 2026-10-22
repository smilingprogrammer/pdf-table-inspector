from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from table_models import TableCandidate
from ..config import ParseConfig


@dataclass(frozen=True)
class PageInput:
    source: Path
    document_id: str
    page: int  # 1-based


@dataclass(frozen=True)
class AdapterResult:
    tables: tuple[TableCandidate, ...] = ()
    # Optional geometric diagnostics; no engine objects cross this boundary.
    diagnostics: dict = field(default_factory=dict)


class TableAdapter(Protocol):
    name: str

    def extract(self, page: PageInput, config: ParseConfig) -> AdapterResult:
        """Return canonical PDF-point candidates; raise on extraction failure.

        Empty tables means a successful run with no tables, never an error.
        Adapters own engine-specific objects, conversion and resource cleanup.
        """
        ...
