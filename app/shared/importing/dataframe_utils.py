"""Helpers to clean tabular data before import."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.shared.utils import parse_str


def unique_or_false(series: pd.Series) -> str | bool:
    """Return the sole unique non-empty value in a column.

    Args:
        series: Column values to inspect for a single unique value.

    Returns:
        The unique string value when only one exists, otherwise False.

    Examples:
        A column with only "A" values returns "A".
    """
    cleaned = series.fillna("").astype(str)
    uniques = cleaned.unique()
    if len(uniques) == 1:
        return parse_str(uniques[0])
    return False


def drop_constant_columns(df: pd.DataFrame, *, log_fn=None) -> pd.DataFrame:
    """Drop columns with a single unique value.

    Args:
        df: Table data to clean.
        log_fn: Logger called with messages about dropped columns when provided.

    Returns:
        A cleaned table without constant columns.
    """
    cols_to_drop: list[str] = []
    for col in df.columns:
        uniq = unique_or_false(df[col])
        if uniq is not False and uniq == "":
            cols_to_drop.append(col)
        elif uniq is not False and uniq != "":
            cols_to_drop.append(col)
            if log_fn:
                log_fn(f"Dropping constant column '{col}' with value '{uniq}'")
    return df.drop(columns=cols_to_drop)
