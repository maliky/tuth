"""General utility helpers shared between apps."""

from datetime import date
from typing import Mapping, Optional

from django.core.management.base import BaseCommand
from tablib import Dataset

from app.shared.constants import STYLE_DEFAULT  # safe


def to_int(value: str | int, default: int = 0) -> int:
    """Lenient int conversion for count-like inputs.

    Args:
        value: Input value to coerce.
        default: Fallback value when parsing fails or input is empty.

    Returns:
        Parsed i#> give examplesnteger value.

    Examples:
        >>> to_int("2.9")
        2
        >>> to_int("", default=5)
        5
    """
    if isinstance(value, int):
        return value
    try:
        return int(float(value))
    except Exception:
        return default


def asserts_keys(required: list[str], row: dict) -> None:
    """Ensure required keys are present in a row.

    Args:
        required: Keys that must exist in the row.
        row: Row data to validate.

    Raises:
        ValueError: If any required key is missing.
    """
    if not all([r in row for r in required]):
        raise ValueError(f"{required} are required in row {row} context.")


def get_in_row(key: str, row: Optional[Mapping[str, str | None]]) -> str:
    """Return a stripped string value from a row.

    Args:
        key: Key to look up in the row.
        row: Row data to read from.

    Returns:
        Stripped value or an empty string when the key is missing or None.

    Raises:
        AttributeError: If the row does not support key lookup.
    """
    try:
        return ((row or {}).get(key) or "").strip()
    except AttributeError as exc:
        raise AttributeError(f"Could not access key '{key}' in row {row}") from exc


def as_title(value: str) -> str:
    """Normalize a string by replacing underscores and title-casing words.

    Args:
        value: Input string to normalize.

    Returns:
        Title-cased string with underscores replaced by spaces.
    """
    return value.replace("_", " ").title()


def clean_column_headers(dataset) -> Dataset:
    """Strip whitespace from dataset headers.

    Args:
        dataset: Tabular data with headers to sanitize.

    Returns:
        The same dataset with cleaned headers.
    """
    sanitised = [(header or "").strip() for header in dataset.headers]
    dataset.headers = sanitised
    return dataset


def parse_int(value: str | None) -> int | None:
    """Convert a value to an integer when possible.

    Args:
        value: Input to parse.

    Returns:
        Parsed integer or None when the input is blank or not numeric.

    Examples:
        >>> parse_int("3.0")
        3
        >>> parse_int("x") is None
        True
    """
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
    """Write a styled message to a management command output.

    Args:
        cmd: Command instance whose stdout and style are used.
        msg: Message to write.
        style: Name of the style attribute to apply.
    """
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))
