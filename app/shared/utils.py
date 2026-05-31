"""General utility helpers shared between apps."""

from datetime import date
from typing import Mapping, Optional

from django.core.management.base import BaseCommand
from tablib import Dataset

from app.shared.constants import STYLE_DEFAULT  # safe


def to_int(value: str | int | None, default: int = 0) -> int:
    """Lenient int conversion for count-like inputs.

    Args:
        value: Input value to coerce.
        default: Fallback value when parsing fails or input is empty.

    Returns:
        Parsed int

    Examples:
        >>> to_int("2.9")
        2
        >>> to_int("", default=5)
        5
    """
    if not value:
        return default

    if isinstance(value, int):
        return value

    token = str(value).strip()
    if not token:
        return default

    try:
        return int(float(token))
    except (TypeError, ValueError):
        return default


def asserts_keys(required: list[str], row: Mapping[str, object] | None) -> None:
    """Ensure required keys are present in a row.

    Args:
        required: Keys that must exist in the row.
        row: Row data to validate.

    Raises:
        ValueError: If any required key is missing.
    """
    safe_row = row or {}
    if not all(r in safe_row for r in required):
        raise ValueError(f"{required} are required in row {row} context.")


def _apply_case(text: str, casing: str) -> str:
    """Return text transformed according to the casing directive."""
    # why not user getattr(text, casting, text) ?
    if casing == "lower":
        return text.lower()
    if casing == "upper":
        return text.upper()
    if casing == "title":
        return text.title()
    if casing == "capitalize":
        return text.capitalize()
    return text


def parse_str(value: object, casing: str = "unchanged", dft: str = "") -> str:
    """Parse an optional string with a default fallback.

    casing: lower, upper, capitalize, title. default unchanged.
    """
    dft_value = _apply_case(dft, casing)
    if value is None:
        return dft_value

    str_value = str(value)
    if not str_value:
        return dft_value

    new_value = _apply_case(str_value, casing).strip()
    return new_value if new_value else dft_value


def get_in_row(key: str, row: Optional[Mapping[str, object | None]]) -> str:
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
        return parse_str((row or {}).get(key))
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
    sanitised = [parse_str(header) for header in dataset.headers]
    dataset.headers = sanitised
    return dataset


def log(cmd: BaseCommand, msg: str, style: str = STYLE_DEFAULT) -> None:
    """Write a styled message to a management command output.

    Args:
        cmd: Command instance whose stdout and style are used.
        msg: Message to write.
        style: Name of the style attribute to apply.
    """
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))
