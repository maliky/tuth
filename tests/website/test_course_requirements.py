"""Tests for grouped curriculum-course requirement evaluation and enforcement."""

from __future__ import annotations

from datetime import datetime
from typing import cast

import pytest
from django.urls import reverse

from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.requirement_group import (
    CurriculumCourseRequirementGroup,
    CurriculumCourseRequirementMember,
    RequirementKind,
)
from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.people.models.student import Student
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from app.website.views.course_requirements import (
    evaluate_curriculum_course_requirements,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_status_defaults() -> None:
    """Create required lookup rows before each test."""
    SemesterStatus._populate_attributes_and_db()
    RegistrationStatus._populate_attributes_and_db()
    InvoiceStatus._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _open_registration_semester(semester_factory) -> Semester:
    """Return one semester marked as registration-open."""
    semester = semester_factory(1, datetime(2026, 1, 1))
    semester.status_id = "registration"
    semester.save(update_fields=["status"])
    return cast(Semester, semester)


def _student_for_curriculum(
    *,
    user_factory,
    curriculum,
    semester: Semester,
    username: str,
) -> Student:
    """Create a student bound to the target curriculum and semester."""
    user = user_factory(username)
    student = Student(
        user=user,
        curriculum=curriculum,
        last_enrolled_semester=semester,
        entry_semester=semester,
    )
    student.save()
    return student


def _add_requirement_member_group(
    *,
    target: CurriculumCourse,
    kind: str,
    required_courses: list[CurriculumCourse],
) -> None:
    """Create one requirement group and populate all member courses."""
    group = CurriculumCourseRequirementGroup.objects.create(
        curriculum_course=target,
        kind=kind,
    )
    for index, required in enumerate(required_courses):
        CurriculumCourseRequirementMember.objects.create(
            group=group,
            required_course=required.course,
            order=index,
        )


def test_requirement_resolver_returns_machine_readable_failure_codes(
    curriculum_course_factory,
    semester_factory,
    user_factory,
) -> None:
    """Resolver should expose all expected failure categories."""
    semester = _open_registration_semester(semester_factory)
    target = curriculum_course_factory("910", "CURRI_REQ")
    target.min_validated_credits = 18
    target.save(update_fields=["min_validated_credits"])
    prereq_all_a = curriculum_course_factory("911", "CURRI_REQ")
    prereq_all_b = curriculum_course_factory("912", "CURRI_REQ")
    prereq_any_a = curriculum_course_factory("913", "CURRI_REQ")
    prereq_any_b = curriculum_course_factory("914", "CURRI_REQ")
    coreq_member = curriculum_course_factory("915", "CURRI_REQ")
    student = _student_for_curriculum(
        user_factory=user_factory,
        curriculum=target.curriculum,
        semester=semester,
        username="req_resolver_student",
    )

    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.PREREQ_ALL,
        required_courses=[prereq_all_a, prereq_all_b],
    )
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.PREREQ_ANY,
        required_courses=[prereq_any_a, prereq_any_b],
    )
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.COREQ_ALL,
        required_courses=[coreq_member],
    )

    result = evaluate_curriculum_course_requirements(
        student=student,
        curriculum_course=target,
        selected_course_ids={target.course_id},
    )
    failure_codes = {failure["code"] for failure in result["failures"]}
    assert not result["ok"]
    assert "missing_credits" in failure_codes
    assert "missing_prereq_all" in failure_codes
    assert "unsatisfied_prereq_any" in failure_codes
    assert "incomplete_coreq_all" in failure_codes


def test_register_post_requires_coreq_group_in_same_action(
    client,
    curriculum_course_factory,
    semester_factory,
    user_factory,
) -> None:
    """Registration POST must reject coreq_all partial selections."""
    semester = _open_registration_semester(semester_factory)
    target = curriculum_course_factory("920", "CURRI_COREQ")
    coreq_member = curriculum_course_factory("921", "CURRI_COREQ")
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.COREQ_ALL,
        required_courses=[coreq_member],
    )
    student = _student_for_curriculum(
        user_factory=user_factory,
        curriculum=target.curriculum,
        semester=semester,
        username="coreq_post_student",
    )
    target_section = Section.objects.create(
        semester=semester,
        curriculum_course=target,
        number=1,
    )
    member_section = Section.objects.create(
        semester=semester,
        curriculum_course=coreq_member,
        number=1,
    )
    client.force_login(student.user)

    blocked_response = client.post(
        reverse("student_dashboard"),
        {
            "action": "register",
            "section_ids": str(target_section.id),
            "semester_id": semester.id,
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    blocked_payload = blocked_response.json()
    assert blocked_response.status_code == 400
    assert "Must be selected together with" in blocked_payload["message"]
    assert not Registration.objects.filter(
        student=student, section=target_section
    ).exists()

    success_response = client.post(
        reverse("student_dashboard"),
        {
            "action": "register",
            "section_ids": f"{target_section.id},{member_section.id}",
            "semester_id": semester.id,
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    success_payload = success_response.json()
    assert success_response.status_code == 200
    assert success_payload["ok"] is True
    assert (
        Registration.objects.filter(
            student=student,
            section__in=[target_section, member_section],
        ).count()
        == 2
    )


def test_dashboard_surfaces_coreq_reason_without_locking_initial_selection(
    client,
    curriculum_course_factory,
    semester_factory,
    user_factory,
) -> None:
    """Dashboard should show coreq guidance while keeping initial course selectable."""
    semester = _open_registration_semester(semester_factory)
    target = curriculum_course_factory("930", "CURRI_COREQ_UI")
    coreq_member = curriculum_course_factory("931", "CURRI_COREQ_UI")
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.COREQ_ALL,
        required_courses=[coreq_member],
    )
    student = _student_for_curriculum(
        user_factory=user_factory,
        curriculum=target.curriculum,
        semester=semester,
        username="coreq_ui_student",
    )
    Section.objects.create(
        semester=semester,
        curriculum_course=target,
        number=1,
    )
    Section.objects.create(
        semester=semester,
        curriculum_course=coreq_member,
        number=1,
    )

    client.force_login(student.user)
    response = client.get(reverse("student_dashboard"), {"semester": semester.id})
    assert response.status_code == 200

    available_courses = response.context["available_courses"]
    target_code = target.course.short_code or target.course.code
    target_payload = next(row for row in available_courses if row["code"] == target_code)
    assert target_payload["eligible"] is True
    assert "Must be selected together with" in target_payload["reason"]
    assert any(
        "Must be selected together with" in line
        for line in target_payload["reason_lines"]
    )


def test_dashboard_surfaces_multiple_requirement_reason_lines(
    client,
    curriculum_course_factory,
    semester_factory,
    user_factory,
) -> None:
    """Locked courses should expose all grouped-requirement reason lines."""
    semester = _open_registration_semester(semester_factory)
    target = curriculum_course_factory("940", "CURRI_REASON_LINES")
    target.min_validated_credits = 24
    target.save(update_fields=["min_validated_credits"])
    req_all = curriculum_course_factory("941", "CURRI_REASON_LINES")
    req_any_a = curriculum_course_factory("942", "CURRI_REASON_LINES")
    req_any_b = curriculum_course_factory("943", "CURRI_REASON_LINES")
    req_all_label = req_all.course.short_code or req_all.course.code
    req_any_a_label = req_any_a.course.short_code or req_any_a.course.code
    req_any_b_label = req_any_b.course.short_code or req_any_b.course.code
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.PREREQ_ALL,
        required_courses=[req_all],
    )
    _add_requirement_member_group(
        target=target,
        kind=RequirementKind.PREREQ_ANY,
        required_courses=[req_any_a, req_any_b],
    )
    student = _student_for_curriculum(
        user_factory=user_factory,
        curriculum=target.curriculum,
        semester=semester,
        username="reason_lines_student",
    )
    Section.objects.create(
        semester=semester,
        curriculum_course=target,
        number=1,
    )

    client.force_login(student.user)
    response = client.get(reverse("student_dashboard"), {"semester": semester.id})
    assert response.status_code == 200

    locked_courses = response.context["locked_courses"]
    target_code = target.course.short_code or target.course.code
    target_payload = next(row for row in locked_courses if row["code"] == target_code)
    assert any(
        "Requires at least 24 validated credits" in line
        for line in target_payload["reason_lines"]
    )
    assert any(
        f"Complete {req_all_label} first." in line
        for line in target_payload["reason_lines"]
    )
    assert any(
        f"Complete at least one of: {req_any_a_label}, {req_any_b_label}." in line
        for line in target_payload["reason_lines"]
    )
