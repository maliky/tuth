"""Faculty grade-entry portal tests."""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest

from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.models.semester import SemesterStatus
from app.timetable.models.section import Section
from app.website.services.faculty_grade_csv import GRADE_CSV_HEADERS
from app.website.services.faculty_grade_portal import GRADE_ENTRY_STATUS, course_code


def _open_grade_entry(section: Section) -> None:
    """Set the section semester to the faculty grade-entry period."""
    SemesterStatus._populate_attributes_and_db()
    section.semester.status_id = GRADE_ENTRY_STATUS
    section.semester.save(update_fields=["status"])


def _make_roster(
    faculty: Faculty,
    sec_factory,
    std_factory,
) -> tuple[Section, Student, Grade]:
    """Create one assigned section with one registered student and grade row."""
    GradeValue._populate_attributes_and_db()
    section = sec_factory("771", "CURRI_FAC_GRADES", 1, 1)
    section.faculty = faculty
    section.save(update_fields=["faculty"])
    student = std_factory("faculty_grade_student", "CURRI_FAC_GRADES")
    student.student_id = "FG-001"
    student.long_name = "Faculty Grade Student"
    student.save(update_fields=["student_id", "long_name"])
    Registration.objects.create(student=student, section=section)
    grade = Grade.objects.create(student=student, section=section)
    return section, student, grade


def _csv_roster_text(*rows: str) -> str:
    """Return a CSV document with the canonical faculty roster headers."""
    return "\n".join([",".join(GRADE_CSV_HEADERS), *rows])


def _csv_upload_row(
    section: Section,
    student: Student,
    grade_code: str,
    *,
    student_id: str | None = None,
    student_name: str | None = None,
    section_id: str | int | None = None,
    section_code: str | None = None,
    course_code_value: str | None = None,
) -> str:
    """Return one roster CSV row, allowing individual identity fields to vary."""
    return ",".join(
        [
            student.student_id if student_id is None else student_id,
            student.long_name if student_name is None else student_name,
            str(section.id if section_id is None else section_id),
            section.short_code if section_code is None else section_code,
            section.semester.academic_year.code,
            str(section.semester.number),
            course_code(section) if course_code_value is None else course_code_value,
            grade_code,
        ]
    )


@pytest.mark.django_db
def test_faculty_grade_sections_show_only_assigned_sections(
    client,
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Faculty section list should not leak another instructor's sections."""
    section, _student, _grade = _make_roster(faculty, sec_factory, std_factory)
    other_faculty = faculty_factory("faculty_grade_other")
    other_section = sec_factory("772", "CURRI_FAC_GRADES_OTHER", 1, 1)
    other_section.faculty = other_faculty
    other_section.save(update_fields=["faculty"])

    client.force_login(faculty.staff_profile.user)
    response = client.get(reverse("faculty_grade_sections"))

    content = response.content.decode()
    assert response.status_code == 200
    assert course_code(section) in content
    assert course_code(other_section) not in content


@pytest.mark.django_db
def test_faculty_roster_uses_autosave_without_visible_bulk_save(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Open rosters should rely on autosave instead of a visible bulk-save button."""
    section, _student, _grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)

    client.force_login(faculty.staff_profile.user)
    response = client.get(reverse("faculty_grade_roster", args=[section.id]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "data-autosave-url" in content
    assert "Save all grades" not in content


@pytest.mark.django_db
def test_faculty_can_save_roster_when_grade_entry_is_open(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Posting the roster form should update grade rows in the database."""
    section, _student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster", args=[section.id]),
        {f"grade_{grade.id}": "a"},
        follow=True,
    )

    grade.refresh_from_db()
    assert response.status_code == 200
    assert grade.value is not None
    assert grade.value.code == "a"


@pytest.mark.django_db
def test_faculty_roster_post_is_blocked_when_grade_entry_is_closed(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Closed semesters should render grades read-only and reject POST edits."""
    section, _student, grade = _make_roster(faculty, sec_factory, std_factory)
    SemesterStatus._populate_attributes_and_db()
    section.semester.status_id = "running"
    section.semester.save(update_fields=["status"])

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster", args=[section.id]),
        {f"grade_{grade.id}": "a"},
        follow=True,
    )

    grade.refresh_from_db()
    assert response.status_code == 200
    assert grade.value is None
    assert "Grade entry is closed" in response.content.decode()


@pytest.mark.django_db
def test_faculty_autosave_updates_one_grade(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """The autosave endpoint should mutate the selected grade row."""
    section, _student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster_autosave", args=[section.id]),
        {"grade_id": grade.id, "grade_code": "b"},
    )

    grade.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert grade.value is not None
    assert grade.value.code == "b"


@pytest.mark.django_db
def test_faculty_can_download_and_upload_csv_roster(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Faculty CSV upload should update roster grades through the portal view."""
    section, student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)

    client.force_login(faculty.staff_profile.user)
    download = client.get(reverse("faculty_grade_roster_download", args=[section.id]))
    assert download.status_code == 200
    assert ",".join(GRADE_CSV_HEADERS) in download.content.decode()
    assert student.student_id in download.content.decode()

    csv_text = _csv_roster_text(_csv_upload_row(section, student, "c"))
    response = client.post(
        reverse("faculty_grade_roster_upload", args=[section.id]),
        {
            "roster_file": SimpleUploadedFile(
                "roster.csv",
                csv_text.encode(),
                content_type="text/csv",
            )
        },
        follow=True,
    )

    grade.refresh_from_db()
    assert response.status_code == 200
    assert grade.value is not None
    assert grade.value.code == "c"


@pytest.mark.django_db
def test_faculty_csv_upload_keeps_blank_grade_as_no_op(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Blank grade rows should import as no-ops so templates can be reused."""
    section, student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)
    csv_text = _csv_roster_text(_csv_upload_row(section, student, ""))

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster_upload", args=[section.id]),
        {
            "roster_file": SimpleUploadedFile(
                "roster.csv",
                csv_text.encode(),
                content_type="text/csv",
            )
        },
        follow=True,
    )

    grade.refresh_from_db()
    assert response.status_code == 200
    assert grade.value is None
    assert "0 grade row(s) imported." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("row_kwargs", "expected_message"),
    [
        ({"section_id": "999999"}, "Section id does not match this roster."),
        ({"section_code": "OTHER-1"}, "Expected section code"),
        ({"course_code_value": "WRONG101"}, "Expected course code"),
        ({"student_id": ""}, "Missing student id."),
        ({"student_name": ""}, "Missing student name."),
        ({"student_name": "Wrong Name"}, "Student name does not match"),
    ],
)
def test_faculty_csv_upload_shows_warning_box_for_identity_errors(
    client,
    faculty,
    sec_factory,
    std_factory,
    row_kwargs,
    expected_message: str,
) -> None:
    """Invalid roster identity fields should render row-level warning feedback."""
    section, student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)
    csv_text = _csv_roster_text(
        _csv_upload_row(section, student, "a", **row_kwargs),
    )

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster_upload", args=[section.id]),
        {
            "roster_file": SimpleUploadedFile(
                "roster.csv",
                csv_text.encode(),
                content_type="text/csv",
            )
        },
    )

    grade.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 400
    assert grade.value is None
    assert "CSV import blocked" in content
    assert expected_message in content


@pytest.mark.django_db
def test_faculty_csv_upload_rejects_duplicate_student_conflicting_grades(
    client,
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Duplicate students with conflicting grades should block the full import."""
    section, student, grade = _make_roster(faculty, sec_factory, std_factory)
    _open_grade_entry(section)
    csv_text = _csv_roster_text(
        _csv_upload_row(section, student, "a"),
        _csv_upload_row(section, student, "b"),
    )

    client.force_login(faculty.staff_profile.user)
    response = client.post(
        reverse("faculty_grade_roster_upload", args=[section.id]),
        {
            "roster_file": SimpleUploadedFile(
                "roster.csv",
                csv_text.encode(),
                content_type="text/csv",
            )
        },
    )

    grade.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 400
    assert grade.value is None
    assert "CSV import blocked" in content
    assert "Duplicate student id also appears on row 2 with a different grade." in content
