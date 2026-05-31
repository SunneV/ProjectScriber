from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SymbolNode:
    name: str
    kind: str  # "class" or "function"
    line_start: int
    line_end: int
    parent_name: str | None = None


@dataclass(slots=True)
class SymbolIndex:
    symbols_by_file: dict[Path, list[SymbolNode]] = field(default_factory=dict)

    def add_symbol(self, file_path: Path, symbol: SymbolNode) -> None:
        self.symbols_by_file.setdefault(file_path, []).append(symbol)

    def get_symbols(self, file_path: Path) -> list[SymbolNode]:
        return self.symbols_by_file.get(file_path, [])
