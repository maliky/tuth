"""Test make_course_code utility."""

from app.shared.utils import make_course_code


def test_make_course_code_without_college():
    assert make_course_code("mat", "101") == "MAT101"


def test_make_course_code_with_college():
    assert make_course_code("mat", "101", "COET") == "MAT101-COET"
