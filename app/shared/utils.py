"""General utility helpers shared between apps."""

from datetime import date
from typing import Mapping, Optional

from django.core.management.base import BaseCommand
from tablib import Dataset

from app.shared.constants import STYLE_DEFAULT  # safe


def get_in_row(key: str, row: Optional[Mapping[str, str | None]]) -> str:
    """Return a value from the row (any mapping) safely stripped to a string.

    Does so safely always returning something even if None is in the row.
    """
    try:
        return ((row or {}).get(key) or "").strip()
    except AttributeError as exc:
        raise AttributeError(f"Could not access key '{key}' in row {row}") from exc


def as_title(value: str) -> str:
    """Utility to clean a strip _ from a str and capitalize its words."""
    return value.replace("_", " ").title()


def clean_column_headers(dataset) -> Dataset:
    """Strip blank headers that may appear due to trailing commas."""
    sanitised = [(header or "").strip() for header in dataset.headers]
    dataset.headers = sanitised
    return dataset


def parse_int(value: str | None) -> int | None:
    """Safely convert arbitrary strings to integers."""
    if value is None:
        return None

    token = str(value).strip()
    if not token:
        return None

    try:
        return int(float(token))
    except ValueError:
        return None


def log(cmd: BaseCommand, msg: str, style: str = STYLE_DEFAULT) -> None:
    """Write a styled message to the management command output."""
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))
