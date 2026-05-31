from __future__ import annotations
from pathlib import Path
from scriber.core.models import FileNode, FileRole, RelationGraph

ROLE_SCORE: dict[FileRole, int] = {
    "entrypoint": 95,
    "orchestrator": 95,
    "graph": 90,
    "ranker": 90,
    "renderer": 90,
    "model": 88,
    "config": 82,
    "scanner": 75,
    "native_adapter": 65,
    "language_adapter": 65,
    "test": 55,
    "support": 45,
    "docs": 35,
    "generated": 5,
    "unknown": 20,
}

def classify_file_role(file: FileNode, graph: RelationGraph) -> FileRole:
    rel = file.relative.as_posix().lower()
    
    if rel in {"cli/main.py", "src/scriber/cli/main.py", "src/main.py", "main.py"}:
        return "entrypoint"
    if "orchestrator" in rel or "pack.py" in rel or "build.py" in rel:
        return "orchestrator"
    if "core/models.py" in rel or "model.py" in rel:
        return "model"
    if "core/config.py" in rel or "config.py" in rel:
        return "config"
    if "test" in rel and file.kind == "code":
        return "test"
    if "languages/" in rel:
        return "language_adapter"
    if "graph/" in rel:
        return "graph"
    if "ranker.py" in rel or "scorer.py" in rel:
        return "ranker"
    if "renderer" in rel or "llm_report" in rel:
        return "renderer"
    if "scanner/" in rel:
        return "scanner"
    if rel.endswith("native.py") or "rust/scriber_native/" in rel or ("native" in rel and file.language == "rust"):
        return "native_adapter"
    if "readme" in rel or rel.startswith("docs"):
        return "docs"
    if rel in {"pyproject.toml", "package.json", "cargo.toml"} or file.kind == "support":
        return "support"
        
    return "unknown"
