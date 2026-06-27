"""Focused tests for prerequisite admin filters."""

import pytest
from django.urls import reverse

from app.academics.models import College, Course, Curriculum, Department, Prerequisite


pytestmark = pytest.mark.django_db


def _course(department: Department, number: str, title: str) -> Course:
    """Create one catalogue course in the supplied department."""
    return Course.objects.create(department=department, number=number, title=title)


def _prerequisite_for_program(
    college_code: str,
    program_code: str,
    course_number: str,
) -> Prerequisite:
    """Create a prerequisite row tied to a distinct college and program."""
    college = College.objects.create(
        code=college_code,
        long_name=f"{college_code} Test College",
    )
    department = Department.objects.create(code=f"{college_code}D", college=college)
    curriculum = Curriculum.objects.create(short_name=program_code, college=college)
    course = _course(department, course_number, f"{program_code} target")
    prereq_course = _course(department, f"{course_number}P", f"{program_code} prereq")
    return Prerequisite.objects.create(
        curriculum=curriculum,
        course=course,
        prerequisite_course=prereq_course,
    )


def _admin_result_ids(client, superuser, params: dict[str, str]) -> set[int]:
    """Return prerequisite ids from the filtered admin changelist."""
    client.force_login(superuser)
    response = client.get(reverse("admin:academics_prerequisite_changelist"), params)
    assert response.status_code == 200
    return {row.id for row in response.context["cl"].result_list}


def test_prerequisite_admin_filters_by_college_and_program(client, superuser):
    """Prerequisites changelist should narrow by college, then by program."""
    cba_prereq = _prerequisite_for_program("TCBA", "TCBA-ACCT", "701")
    cas_prereq = _prerequisite_for_program("TCAS", "TCAS-BIOL", "801")
    assert cba_prereq.curriculum is not None
    assert cas_prereq.curriculum is not None

    college_ids = _admin_result_ids(
        client,
        superuser,
        {"curriculum__college": str(cba_prereq.curriculum.college_id)},
    )
    assert college_ids == {cba_prereq.id}

    program_ids = _admin_result_ids(
        client,
        superuser,
        {"curriculum": str(cas_prereq.curriculum_id)},
    )
    assert program_ids == {cas_prereq.id}
