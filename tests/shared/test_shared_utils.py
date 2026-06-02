"""Test shared utils module."""

from typing import Any

import pytest

from app.academics.models.college import College
from app.academics.utils import expand_crs_code
from app.shared.auth import perms

# from tests.fixtures.academics import dpt_factory, college


def test_expand_code_explicit_college():
    result = expand_crs_code("COET-MATH101", row={"college_code": "COAS"})
    assert result == (
        "COET",
        "MATH",
        "101",
    )


def test_expand_code_dfts_to_row_college():
    college, dept, num = expand_crs_code("CHEM100", row={"college_code": "COAS"})
    assert (college, dept, num) == ("COAS", "CHEM", "100")


@pytest.mark.django_db
def test_expand_code_to_dfts_when_row_missing(college, dpt_factory):
    dept = dpt_factory("BIOL")

    dft_college = College.get_dft()

    college_code, dept_code, num = expand_crs_code("BIOL105")

    assert college_code == dft_college.code
    assert dept_code == dept.code
    assert num == "105"


def test_expand_code_invalid_format():
    with pytest.raises(AssertionError):
        expand_crs_code("MATH/101")


@pytest.mark.django_db
def test_expand_code_accepts_underscore(college, dpt_factory):
    dept = dpt_factory("ACCT")
    college_code, dept_shortname, num = expand_crs_code("ACCT_404")

    assert college_code == college.code
    assert dept_shortname == dept.code
    assert num == "404"


def test_validate_role_matrix(monkeypatch):
    """Check the return value if everything is fine."""
    expected: dict[str, dict[Any, Any]] = {ur.value.code: {} for ur in perms.UserRole}
    # Monkeypatch isolates ROLE_MATRIX changes to this test only.
    monkeypatch.setattr(perms, "ROLE_MATRIX", expected)
    assert perms.validate_role_matrix() == set()


def test_validate_role():
    """Check the Userrole.code and role_matrix."""
    assert perms.validate_role_matrix() == set()
