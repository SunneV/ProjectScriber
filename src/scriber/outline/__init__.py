from scriber.core.models import FileNode, FileOutline
from scriber.outline.base import Outliner
from scriber.outline.generic import GenericOutliner
from scriber.outline.python import PythonOutliner

_outliners: dict[str, Outliner] = {
    "python": PythonOutliner(),
}
_generic = GenericOutliner()

def generate_outline(file: FileNode, content: str) -> FileOutline:
    outliner = _outliners.get(file.language, _generic)
    return outliner.outline(file, content)
