from __future__ import annotations

from typing import Any

_NATIVE_MODULE = None
_IMPORT_ERROR = None


def _load_native() -> Any:
    global _NATIVE_MODULE, _IMPORT_ERROR
    if _NATIVE_MODULE is not None:
        return _NATIVE_MODULE
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR
    try:
        from scriber import _native

        _NATIVE_MODULE = _native
        return _NATIVE_MODULE
    except ImportError as e:
        _IMPORT_ERROR = e
        raise e


def is_native_available() -> bool:
    """Returns True if the native Rust module scriber._native is available."""
    try:
        _load_native()
        return True
    except ImportError:
        return False


def require_native() -> Any:
    """Returns the native Rust module _native or raises ImportError with instructions."""
    try:
        native = _load_native()
        if hasattr(native, "native_api_version") and native.native_api_version() != 1:
            raise RuntimeError(
                "Niezgodna wersja natywnego backendu Scriber (oczekiwano wersji 1)."
            )
        return native
    except ImportError as e:
        raise ImportError(
            "Natywny moduł 'scriber._native' nie jest dostępny.\n"
            "Upewnij się, że projekt został poprawnie skompilowany "
            "za pomocą 'uv run maturin develop' lub 'uv sync'."
        ) from e
