"""Helpers to clean pandas DataFrames before import."""

from __future__ import annotations

from typing import Any

import pandas as pd


def unique_or_false(series: pd.Series) -> str | bool:
    """Return the sole unique non-NaN value, or False if multiple/none."""
    cleaned = series.fillna("").astype(str)
    uniques = cleaned.unique()
    if len(uniques) == 1:
        value = uniques[0].strip()
        return value or ""
    return False


def drop_constant_columns(df: pd.DataFrame, *, log_fn=None) -> pd.DataFrame:
    """Drop columns with a single unique value; log non-empty constants."""
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
