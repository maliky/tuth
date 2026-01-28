"""Utilities for building import-friendly seed datasets."""

from . import academics, people, registry_finance, spaces, timetable
from .loaders import load_csv, load_xls, peek_in

__all__ = [
    "load_csv",
    "load_xls",
    "peek_in",
    "academics",
    "people",
    "registry_finance",
    "spaces",
    "timetable",
]
