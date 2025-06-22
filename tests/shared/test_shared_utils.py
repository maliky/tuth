"""Test shared utils module."""

import pytest

from app.shared.utils import expand_course_code

# from tests.fixtures.academics import department_factory, college


def test_expand_code_explicit_college():
    result = expand_course_code("COET-MATH101", row={"college_code": "COAS"})
    assert result == (
        "COET",
        "MATH",
        "101",
    )


def test_expand_code_defaults_to_row_college():
    college, dept, num = expand_course_code("CHEM100", row={"college_code": "COAS"})
    assert (college, dept, num) == ("COAS", "CHEM", "100")


@pytest.mark.django_db
def test_expand_code_defaults_to_coas_when_row_missing(college, department_factory):
    dept = department_factory("BIOL")

    college_code, dept_code, num = expand_course_code("BIOL105")

    assert college_code == "COAS", f"college.code=>{college.code}"
    assert dept_code == dept.code
    assert num == "105"


def test_expand_code_invalid_format():
    with pytest.raises(AssertionError):
        expand_course_code("MATH/101")


@pytest.mark.django_db
def test_expand_code_accepts_underscore(college, department_factory):

    dept = department_factory("ACCT")
    college_code, dept_code, num = expand_course_code("ACCT_404")

    assert college_code == college.code
    assert dept_code == dept.code
    assert num == "404"
