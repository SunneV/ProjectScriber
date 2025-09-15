"""
ProjectScriber: A tool for mapping and compiling project source code.

This package provides the core functionality and command-line interface for
ProjectScriber. The main `Scriber` class can be imported directly for
programmatic use.
"""
from .core import Scriber, ScriberConfig

__all__ = ["Scriber", "ScriberConfig"]