from __future__ import annotations
import ast
from scriber.core.models import FileNode, FileOutline
from scriber.outline.base import Outliner


class PythonOutliner(Outliner):
    def outline(self, file: FileNode, content: str) -> FileOutline:
        classes = []
        functions = []
        imports = []
        try:
            tree = ast.parse(content)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
        except SyntaxError:
            pass

        return FileOutline(
            path=file.relative,
            language="python",
            purpose=None,
            imports=imports[:20],
            exports=[],
            classes=classes,
            functions=functions,
            constants=[],
            notes=[],
            token_estimate=len(classes) * 5 + len(functions) * 3 + len(imports) * 2,
        )
