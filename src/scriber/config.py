"""
Configuration data structure for the Scriber application.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Set

_DEFAULT_OUTPUT_FILENAME = "scriber_output.txt"
_CONFIG_FILE_NAME = ".scriber.json"


@dataclass
class ScriberConfig:
    """
    A dataclass to hold all configuration settings for Scriber.

    This provides a structured, type-safe way to manage configuration,
    replacing the previous dictionary-based approach. It includes methods
    for easy conversion to and from dictionaries.
    """
    use_gitignore: bool = True
    exclude: List[str] = field(default_factory=lambda: [
        "LICENSE",
        ".git/",
        ".idea/", ".vscode/", ".project/", ".settings/", ".classpath/",
        "__pycache__/", "*.pyc", ".venv/", "venv/", ".pytest_cache/", "uv.lock",
        "node_modules/", "npm-debug.log*", "yarn-error.log",
        "build/", "dist/", "target/", "bin/", "obj/", "out/",
        "vendor/", "bower_components/",
        "*.log", "*.lock", "*.tmp", "temp/", "tmp/",
        ".DS_Store", "Thumbs.db", "*~", "*.swp", "*.swo",
        _DEFAULT_OUTPUT_FILENAME, _CONFIG_FILE_NAME
    ])
    include: List[str] = field(default_factory=list)
    hidden: List[str] = field(default_factory=list)
    exclude_map: Dict[str, List[str]] = field(default_factory=dict)
    output: str = _DEFAULT_OUTPUT_FILENAME
    single_process: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the configuration dataclass to a dictionary.

        Returns:
            A dictionary representation of the configuration settings.
        """
        return asdict(self)