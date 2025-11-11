"""Test shared utils module."""
from typing import Any
from app.academics.models.college import College
import pytest
from app.shared.auth import perms
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
def test_expand_code_to_defaults_when_row_missing(college, department_factory):
    dept = department_factory("BIOL")

    dft_college = College.get_default()

    college_code, dept_short_name, num = expand_course_code("BIOL105")

    assert college_code == dft_college.code
    assert dept_short_name == dept.short_name
    assert num == "105"


def test_expand_code_invalid_format():
    with pytest.raises(AssertionError):
        expand_course_code("MATH/101")


@pytest.mark.django_db
def test_expand_code_accepts_underscore(college, department_factory):

    dept = department_factory("ACCT")
    college_code, dept_short_name, num = expand_course_code("ACCT_404")

    assert college_code == college.code
    assert dept_short_name == dept.short_name
    assert num == "404"


def test_validate_role_matrix(monkeypatch):
    """Check the return value if everything is fine."""
    expected: dict[str, dict[Any, Any]] = {ur.value.code: {} for ur in perms.UserRole}
    monkeypatch.setattr(perms, "ROLE_MATRIX", expected)
    assert perms.validate_role_matrix() == set()


def test_validate_role():
    """Check the Userrole.code and role_matrix."""
    assert perms.validate_role_matrix() == set()
