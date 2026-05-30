from __future__ import annotations

from pathlib import Path

from .errors import ScriberError


def resolve_config_path(paths: list[str], explicit_config: str | None = None) -> Path:
    if explicit_config:
        config = Path(explicit_config).expanduser()
        if config.is_dir():
            config = config / "pyproject.toml"
        if not config.is_absolute():
            config = Path.cwd() / config
        config = config.resolve()
        if not config.exists():
            raise ScriberError(f"Config not found: {config}")
        if config.name != "pyproject.toml":
            raise ScriberError("Scriber 2.0 expects --config to point to pyproject.toml")
        return config

    starts: list[Path] = []
    for raw in paths or ["."]:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        # We allow paths that do not exist to report a better error later, but
        # root discovery should still start from the nearest existing parent.
        probe = path.resolve(strict=False)
        if probe.exists() and probe.is_file():
            probe = probe.parent
        elif not probe.exists() and probe.suffix:
            probe = probe.parent
        starts.append(probe)
    starts.append(Path.cwd().resolve())

    seen: set[Path] = set()
    for start in starts:
        for parent in [start, *start.parents]:
            if parent in seen:
                continue
            seen.add(parent)
            candidate = parent / "pyproject.toml"
            if candidate.exists():
                return candidate.resolve()

    raise ScriberError("No pyproject.toml found. Run `scriber init` or pass `--config /path/to/pyproject.toml`.")


def project_root_from_config(config_path: Path) -> Path:
    return config_path.resolve().parent


def ensure_inside_root(path: Path, root: Path, allow_external: bool) -> None:
    if allow_external:
        return
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ScriberError(f"Path is outside project root: {path}") from exc


def rel_to_root(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path.resolve()
