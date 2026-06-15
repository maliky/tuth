"""Student-facing course information page regressions."""

from __future__ import annotations

from datetime import datetime

import pytest
from django.urls import reverse

from app.academics.models import College, Course, CurriCrs, Curriculum, Department
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriCrsReqGp,
    CurriCrsReqMember,
    ReqKind,
)
from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.models.section import Section
from app.timetable.models.semester import SemesterStatus
from app.website.services.student_course_info import build_student_course_info

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_course_info_dfts() -> None:
    """Create lookup rows required by student course-info views."""
    SemesterStatus._populate_attributes_and_db()
    RegistrationStatus._populate_attributes_and_db()
    InvoiceStatus._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _set_course_text(curriculum_course, title: str, description: str = "") -> None:
    """Apply readable course text for assertions."""
    course = curriculum_course.course
    course.title = title
    course.description = description
    course.save(update_fields=["title", "description"])


def _course_info_setup(
    *,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> tuple[Student, Section, CurriCrs, CurriCrs, CurriCrs, CurriCrs]:
    """Build one curriculum graph for student course information tests."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    semester.status_id = "registration"
    semester.save(update_fields=["status"])
    target = curriculum_course_factory("931", "CURRI_STUDENT_INFO")
    prereq = curriculum_course_factory("932", "CURRI_STUDENT_INFO")
    coreq = curriculum_course_factory("933", "CURRI_STUDENT_INFO")
    unlocked = curriculum_course_factory("934", "CURRI_STUDENT_INFO")
    _set_course_text(target, "Teaching Methods", "Methods course description.")
    _set_course_text(prereq, "Education Foundations")
    _set_course_text(coreq, "Teaching Lab")
    _set_course_text(unlocked, "Teaching Practicum")
    Prerequisite.objects.create(
        curriculum=target.curriculum,
        course=target.course,
        prerequisite_course=prereq.course,
    )
    coreq_group = CurriCrsReqGp.objects.create(
        curriculum_course=target,
        kind=ReqKind.COREQ_ALL,
        label="Field pair",
    )
    CurriCrsReqMember.objects.create(
        group=coreq_group,
        required_course=coreq.course,
    )
    Prerequisite.objects.create(
        curriculum=target.curriculum,
        course=unlocked.course,
        prerequisite_course=target.course,
    )
    user = user_factory("student_course_info")
    student = Student(user=user, last_enrolled_semester=semester)
    student.save()
    set_primary_std_curri_enroll(student, target.curriculum)
    section = Section.objects.create(
        semester=semester,
        curriculum_course=target,
        number=1,
    )
    Registration.objects.create(
        student=student,
        section=section,
        status=RegistrationStatus.pending(),
    )
    return student, section, target, prereq, coreq, unlocked


def test_student_section_detail_shows_course_information_for_pending_registration(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Pending student registrations should expose course details."""
    student, section, _target, prereq, coreq, unlocked = _course_info_setup(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
    )

    client.force_login(student.user)
    response = client.get(reverse("std_sec_detail", args=[section.id]))

    assert response.status_code == 200
    assert b"Methods course description." in response.content
    assert (
        prereq.course.short_code or prereq.course.code or ""
    ).encode() in response.content
    assert (
        coreq.course.short_code or coreq.course.code or ""
    ).encode() in response.content
    assert (
        unlocked.course.short_code or unlocked.course.code or ""
    ).encode() in response.content
    assert b"Courses unlocked by this course" in response.content


def test_student_section_detail_rejects_other_students_registration(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Students must not open section details for another student's registration."""
    _student, section, target, _prereq, _coreq, _unlocked = _course_info_setup(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
    )
    other_user = user_factory("student_course_info_other")
    other_student = Student(user=other_user, last_enrolled_semester=section.semester)
    other_student.save()
    set_primary_std_curri_enroll(other_student, target.curriculum)

    client.force_login(other_user)
    response = client.get(reverse("std_sec_detail", args=[section.id]))

    assert response.status_code == 404


def test_student_dashboard_course_cards_link_to_curriculum_detail(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Available course cards should link to the shared course detail page."""
    student, _section, _target, _prereq, _coreq, unlocked = _course_info_setup(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
    )

    client.force_login(student.user)
    response = client.get(reverse("student_dashboard"))

    assert response.status_code == 200
    assert (
        reverse("std_curri_crs_detail", args=[unlocked.id]).encode() in response.content
    )


def test_student_course_info_marks_duplicate_key_prereq_completed(
    sem_factory,
    user_factory,
) -> None:
    """Prerequisite completion should compare course keys, not fragile Course ids."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    curriculum = Curriculum.objects.create(
        short_name="CURRI_DUP_KEY",
        college=College.get_dft(),
    )
    source_college = College.objects.create(code="SRC", long_name="Source College")
    legacy_college = College.objects.create(code="LEG", long_name="Legacy College")
    source_math = Department.objects.create(code="MATH", college=source_college)
    legacy_math = Department.objects.create(code="MATH", college=legacy_college)
    target_dept = Department.get_dft("TGT")
    target_course = Course.objects.create(
        department=target_dept,
        number="201",
        title="Target course",
    )
    prereq_display_course = Course.objects.create(
        department=source_math,
        number="101",
        title="College Algebra",
    )
    prereq_passed_course = Course.objects.create(
        department=legacy_math,
        number="101",
        title="College Algebra",
    )
    target_cc = CurriCrs.objects.create(curriculum=curriculum, course=target_course)
    passed_cc = CurriCrs.objects.create(
        curriculum=curriculum,
        course=prereq_passed_course,
    )
    Prerequisite.objects.create(
        curriculum=None,
        course=target_course,
        prerequisite_course=prereq_display_course,
    )
    user = user_factory("student_duplicate_key_prereq")
    student = Student(user=user, last_enrolled_semester=semester)
    student.save()
    passed_section = Section.objects.create(
        semester=semester,
        curriculum_course=passed_cc,
        number=1,
    )
    Grade.objects.create(
        student=student,
        section=passed_section,
        value=GradeValue.objects.create(code="a"),
    )

    course_info = build_student_course_info(
        student=student,
        curriculum_course=target_cc,
    )

    assert course_info["prerequisites"][0]["code"] == "MATH101"
    assert course_info["prerequisites"][0]["status_label"] == "Completed"
