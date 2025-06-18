"""Test shared utils module."""

import pytest

from app.shared.utils import expand_course_code


def test_expand_code_explicit_college():
    result = expand_course_code("MATH101 - COET", row={"college_code": "COAS"})
    assert result == ("MATH", "101", "COET")


def test_expand_code_defaults_to_row_college():
    dept, num, college = expand_course_code(
        "CHEM100", row={"college_code": "COAS"}
    )
    assert (dept, num, college) == ("CHEM", "100", "COAS")


def test_expand_code_defaults_to_coas_when_row_missing():
    dept, num, college = expand_course_code("BIOL105")
    assert college == "COAS"


def test_expand_code_invalid_format():
    with pytest.raises(AssertionError):
        expand_course_code("MATH/101")


def test_expand_code_accepts_underscore():
    dept, num, college = expand_course_code("ACCT_404")
    assert (dept, num, college) == ("ACCT", "404", "COAS")
