"""Compatibility helpers for django-import-export resources."""

from __future__ import annotations

from typing import TypeAlias

from tablib import Dataset

ImportDefaultT: TypeAlias = str | bool | int


def ensure_dataset_column(
    dataset: Dataset,
    column_name: str,
    default: ImportDefaultT,
) -> None:
    """Add a default column when legacy import files omit a new field."""
    headers = list(dataset.headers or [])
    if column_name in headers:
        return
    if dataset.headers is None:
        dataset.headers = headers
    # import-export validates declared fields against headers before row defaults.
    dataset.append_col([default] * len(dataset), header=column_name)


__all__ = ["ImportDefaultT", "ensure_dataset_column"]
