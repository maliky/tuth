"""Test shared utils module."""

from typing import Any

import pytest

from app.academics.models.college import College
from app.academics.utils import expand_crs_code
from app.shared.auth import perms
from app.shared.importing.rows import (
    normalize_course_number,
    parse_course_identity,
    parse_course_identity_result,
)

# from tests.fixtures.academics import dpt_factory, college


def test_expand_code_explicit_college():
    result = expand_crs_code("COET-MATH101", row={"college_code": "COAS"})
    assert result == (
        "CET",
        "MATH",
        "101",
    )


def test_expand_code_dfts_to_row_college():
    college, dept, num = expand_crs_code("CHEM100", row={"college_code": "COAS"})
    assert (college, dept, num) == ("CAS", "CHEM", "100")


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


def test_course_identity_parser_handles_dirty_smartschool_codes():
    """Shared import parser should repair recoverable legacy course codes."""
    assert parse_course_identity("MATH", "003") == ("MATH", "003")
    assert parse_course_identity("Math 003", "Math 003") == ("MATH", "003")
    assert parse_course_identity("MENG", "301A") == ("MENG", "301A")
    assert parse_course_identity("AGR", "403(A)") == ("AGR", "403A")
    assert parse_course_identity("CSENG", "301") == ("CSENG", "301")
    assert parse_course_identity("MATH", "3") == ("MATH", "003")
    assert parse_course_identity("PH", "102") == ("PH", "102")
    assert parse_course_identity("ME", "ME") is None
    assert normalize_course_number("101.0") == "101"
    repaired = parse_course_identity_result("MATH", "3")
    assert repaired is not None
    assert repaired.repair_reason == "legacy_padded_number"


def test_expand_code_accepts_spaced_legacy_code():
    """Existing expand_crs_code behavior now accepts spaced legacy codes."""
    college, dept, num = expand_crs_code("MATH 003", row={"college_code": "COAS"})
    assert (college, dept, num) == ("CAS", "MATH", "003")


def test_expand_code_uses_edrce_for_education_aliases():
    """Education aliases should resolve to the TU-used EDRCE acronym."""
    assert expand_crs_code("EDU101", row={"college_code": "CED"}) == (
        "EDRCE",
        "EDU",
        "101",
    )
    assert expand_crs_code("EDU102", row={"college_code": "COED"}) == (
        "EDRCE",
        "EDU",
        "102",
    )


def test_expand_code_accepts_tucurricula_shape():
    """TUCurricula course codes allow 3-5 letters and an optional suffix."""
    assert expand_crs_code("CENG410A", row={"college_code": "COET"}) == (
        "CET",
        "CENG",
        "410A",
    )
    assert expand_crs_code("CSENG 301", row={"college_code": "COET"}) == (
        "CET",
        "CSENG",
        "301",
    )
    assert expand_crs_code("EENG  310", row={"college_code": "COET"}) == (
        "CET",
        "EENG",
        "310",
    )


def test_validate_role_matrix(monkeypatch):
    """Check the return value if everything is fine."""
    expected: dict[str, dict[Any, Any]] = {ur.value.code: {} for ur in perms.UserRole}
    # Monkeypatch isolates ROLE_MATRIX changes to this test only.
    monkeypatch.setattr(perms, "ROLE_MATRIX", expected)
    assert perms.validate_role_matrix() == set()


def test_validate_role():
    """Check the Userrole.code and role_matrix."""
    assert perms.validate_role_matrix() == set()
