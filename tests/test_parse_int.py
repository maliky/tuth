"""Test parse_int utility."""

import pytest

from app.shared.management.populate_helpers.sections import parse_int


def test_parse_int_numeric_values():
    assert parse_int("42") == 42
    assert parse_int("1.0") == 1
    assert parse_int(" 3.5 ") == 3


def test_parse_int_non_numeric_values():
    assert parse_int(None) is None
    assert parse_int("abc") is None
    assert parse_int("") is None
