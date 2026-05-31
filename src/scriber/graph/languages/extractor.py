import ast
from pathlib import Path
from typing import Any
from scriber.core.symbols import SymbolNode, SymbolIndex


class PythonSymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, index: SymbolIndex):
        self.file_path = file_path
        self.index = index
        self.current_parent: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        start = node.lineno
        end = getattr(node, "end_lineno", start)

        symbol = SymbolNode(
            name=node.name,
            kind="class",
            line_start=start,
            line_end=end,
            parent_name=self.current_parent,
        )
        self.index.add_symbol(self.file_path, symbol)

        old_parent = self.current_parent
        self.current_parent = node.name
        self.generic_visit(node)
        self.current_parent = old_parent

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        start = node.lineno
        end = getattr(node, "end_lineno", start)

        symbol = SymbolNode(
            name=node.name,
            kind="function",
            line_start=start,
            line_end=end,
            parent_name=self.current_parent,
        )
        self.index.add_symbol(self.file_path, symbol)

        old_parent = self.current_parent
        self.current_parent = node.name
        self.generic_visit(node)
        self.current_parent = old_parent

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        start = node.lineno
        end = getattr(node, "end_lineno", start)

        symbol = SymbolNode(
            name=node.name,
            kind="function",
            line_start=start,
            line_end=end,
            parent_name=self.current_parent,
        )
        self.index.add_symbol(self.file_path, symbol)

        old_parent = self.current_parent
        self.current_parent = node.name
        self.generic_visit(node)
        self.current_parent = old_parent


def extract_python_symbols(
    file_path: Path, source_code: str, index: SymbolIndex
) -> None:
    try:
        tree = ast.parse(source_code, filename=str(file_path))
        visitor = PythonSymbolVisitor(file_path, index)
        visitor.visit(tree)
    except Exception:
        # Gracefully handle syntactically invalid or unparseable files
        pass
