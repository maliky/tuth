"""Shared data-loading helpers for the Seed_data build pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def load_csv(
    filename: str | Path,
    *,
    encoding: str = "utf-16-le",
    sep: str = "\t",
    drop_empty_columns: bool = True,
    low_memory: bool = False,
    **pandas_kwargs: Any,
) -> pd.DataFrame:
    """Return a dataframe from a CSV/TSV, trimming all-null columns by default."""
    df = pd.read_csv(
        filename,
        sep=sep,
        encoding=encoding,
        low_memory=low_memory,
        **pandas_kwargs,
    )
    if drop_empty_columns:
        df = df.drop(columns=df.columns[df.isna().all()])
    return df


def load_xls(
    filename: str | Path,
    *,
    sheet_kwargs: Dict[str, Any] | None = None,
    **excel_kwargs: Any,
) -> dict[str, pd.DataFrame]:
    """Load every sheet of the workbook into a dict keyed by sheet name."""
    sheet_kwargs = sheet_kwargs or {}
    xls = pd.ExcelFile(filename, **excel_kwargs)
    return {
        sheet_name: pd.read_excel(xls, sheet_name=sheet_name, **sheet_kwargs)
        for sheet_name in xls.sheet_names
    }


def peek_in(df: pd.DataFrame, limit: int = 33) -> tuple[str, dict[str, str]]:
    """Summarize dataframe cardinalities like the original notebook helper."""
    details: dict[str, str] = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            details[col] = ""
            continue

        counts = series.value_counts().sort_values(ascending=False)
        sample = counts.iloc[:limit]
        key = f"{col} ({series.nunique()})"
        if series.nunique() == len(df):
            values = [str(v) for v in sample.index]
            key = f"{col}_id ({series.nunique()})"
        else:
            values = [f"{value} ({count})" for value, count in sample.items()]
        details[key] = ", ".join(values)

    return f"len={len(df)}", details
