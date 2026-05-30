from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path


def open_path(path: Path) -> None:
    if not path.exists():
        return

    path_str = str(path.resolve())
    try:
        if sys.platform == "win32":
            os.startfile(path_str)
        elif sys.platform == "darwin":
            subprocess.run(["open", path_str], check=True)
        else:
            subprocess.run(["xdg-open", path_str], check=True)
    except Exception as exc:
        sys.stderr.write(f"Warning: Failed to open pack file: {exc}\n")
