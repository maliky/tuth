"""Registrar transcript document regressions."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.student import Student
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.transcript_document import build_transcript_document
from app.website.services.transcript_rendering import (
    render_transcript_document_html,
    render_transcript_document_org,
)

pytestmark = pytest.mark.django_db


def _grade_value(code: str) -> GradeValue:
    """Return a grade value with normalized numeric points."""
    grade_value, _created = GradeValue.objects.get_or_create(code=code)
    return grade_value


def _grant_grade_view(user) -> None:
    """Grant broad grade visibility without registrar role membership."""
    user.user_permissions.add(Permission.objects.get(codename="view_grade"))


def _history_section(
    semester: Semester,
    curriculum: Curriculum,
    code: str,
    title: str,
) -> Section:
    """Create a section for transcript alias tests."""
    dept = Department.get_dft("HIST")
    course, _created = Course.objects.get_or_create(
        department=dept,
        number=code,
        defaults={"title": title},
    )
    course.title = title
    course.save(update_fields=["title"])
    curriculum_course, _created = CurriCrs.objects.get_or_create(
        curriculum=curriculum,
        course=course,
        defaults={"credit_hours": CreditHour.objects.get(code=3)},
    )
    return Section.objects.create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=1,
    )


def test_transcript_document_counts_failed_courses_as_attempted_not_earned(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Failed grades should affect attempted credits and GPA, not earned credits."""
    _academic_year, previous, current = reg_sem_pair_factory()
    pass_section, curriculum = reg_sec_factory(
        previous,
        course_number="301",
        curriculum_short_name="CURRI_TRANSCRIPT",
    )
    fail_section, _curriculum = reg_sec_factory(
        current,
        course_number="302",
        curriculum_short_name="CURRI_TRANSCRIPT",
    )
    student = reg_std_factory("registrar_transcript_failed", curriculum, previous)
    Grade.objects.create(student=student, section=pass_section, value=_grade_value("a"))
    Grade.objects.create(student=student, section=fail_section, value=_grade_value("f"))

    document = build_transcript_document(student.id)

    assert document["program_total_attempted"] == "6"
    assert document["program_total_earned"] == "3"
    assert document["cumulative_total_quality"] == "12"
    assert document["cumulative_total_gpa"] == "2.00"


def test_transcript_document_collapses_approved_duplicate_aliases(
    reg_sem_pair_factory,
    reg_std_factory,
) -> None:
    """Approved historical aliases should keep only the effective transcript grade."""
    _academic_year, previous, current = reg_sem_pair_factory()
    curriculum = Curriculum.get_dft("CURRI_TRANSCRIPT_ALIAS")
    student = reg_std_factory("registrar_transcript_alias", curriculum, previous)
    older_section = _history_section(previous, curriculum, "101", "Liberian History")
    newer_section = _history_section(current, curriculum, "201", "Liberian History")
    Grade.objects.create(student=student, section=older_section, value=_grade_value("b"))
    Grade.objects.create(student=student, section=newer_section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    rows = [row for group in document["term_groups"] for row in group["rows"]]

    assert len(rows) == 1
    assert rows[0]["course_code"] == "HIST201"
    assert document["program_total_attempted"] == "3"
    assert document["cumulative_total_quality"] == "12"


def test_registrar_transcript_pdf_download_uses_pdf_response(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar users can download a generated transcript PDF."""
    user = reg_user_factory("registrar_transcript_pdf")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="401",
        curriculum_short_name="CURRI_TRANSCRIPT_PDF",
    )
    student = reg_std_factory("registrar_transcript_pdf_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)
    response = client.get(reverse("reg_grade_transcript_pdf", args=[student.id]))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF")


def test_transcript_pdf_html_uses_layout_selection_and_compact_grade_table(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """The PDF source should use selected layout and no date-column grade table."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="403",
        curriculum_short_name="CURRI_TRANSCRIPT_HTML",
    )
    section.start_date = date(2026, 3, 4)
    section.end_date = date(2026, 5, 6)
    section.save(update_fields=["start_date", "end_date"])
    student = reg_std_factory("registrar_transcript_html_student", curriculum, current)
    student.physical_address = "Hoffman Station, Harper City\nMaryland County, Liberia"
    student.birth_date = date(1982, 5, 17)
    student.save(update_fields=["physical_address", "birth_date"])
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    html = render_transcript_document_html(document, layout="landscape_two")

    assert "@bottom-center" in html
    assert "Registrar signature / Date" in html
    assert "Printed on" not in html
    assert "Clinical" not in html
    assert "Attmpt Credit" not in html
    assert "Start Date" not in html
    assert "End Date" not in html
    assert "Attempted<br/>Credit" in html
    assert 'class="logo-block"' in html
    assert 'class="institution-contact"' in html
    assert 'class="student-meta"' in html
    assert 'data-transcript-layout="landscape_two"' in html
    assert "size: A4 landscape;" in html
    assert 'class="summary-metrics"' in html
    assert 'class="totals-table summary-totals"' not in html
    assert "04/03/26" not in html
    assert "06/05/26" not in html
    assert "Maryland County, Republic of Liberia" in html
    assert "www.Tubmanu.edu.lr · registrar@tubmanu.edu.lr" in html
    assert "institution-document-title" in html
    assert html.count("Maryland County, Liberia") == 1
    assert "Transcript Back Matter" in html
    assert "Grade Letters and Credit Points" in html
    assert "Mention and honor thresholds" in html
    assert "Online transcript verification link" in html


def test_registrar_transcript_org_download_uses_source_response(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar users can download a LaTeX-exportable Org transcript source."""
    user = reg_user_factory("registrar_transcript_org")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="404",
        curriculum_short_name="CURRI_TRANSCRIPT_ORG",
    )
    student = reg_std_factory("registrar_transcript_org_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)
    response = client.get(reverse("reg_grade_transcript_org", args=[student.id]))
    org_source = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Type"] == "application/octet-stream"
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["Content-Disposition"].endswith('.org"')
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Length"] == str(len(response.content))
    assert "#+LATEX_CLASS: tutranscript" in org_source
    assert "#+LATEX_COMPILER: lualatex" in org_source
    assert "\\TUTranscriptCourse" in org_source
    assert "Attmpt Credit" not in org_source
    assert "Start Date" not in org_source
    assert "End Date" not in org_source
    assert "\\TUPrintTranscript" in org_source
    assert "Clinical" not in org_source


def test_registrar_transcript_page_shows_body_download_actions(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """The transcript preview should expose downloads inside the page body."""
    user = reg_user_factory("registrar_transcript_actions")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="408",
        curriculum_short_name="CURRI_TRANSCRIPT_ACTIONS",
    )
    student = reg_std_factory("registrar_transcript_actions_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)
    response = client.get(reverse("reg_grade_transcript", args=[student.id]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Transcript exports" in content
    assert "data-transcript-layout-select" in content
    assert "Portrait - one grade column" in content
    assert "Landscape - two grade columns" in content
    assert "Download Org source" in content
    assert "data-transcript-org-download" in content


def test_transcript_org_renderer_escapes_latex_values(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Generated Org should keep unsafe transcript text inside escaped macros."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="405",
        curriculum_short_name="CURRI_TRANSCRIPT_ESCAPE",
    )
    section.curriculum_course.course.title = "Research & Writing_101"
    section.curriculum_course.course.save(update_fields=["title"])
    student = reg_std_factory("registrar_transcript_escape_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    org_source = render_transcript_document_org(build_transcript_document(student.id))

    assert r"Research \& Writing\_101" in org_source


def test_transcript_template_pack_contains_org_latex_sources() -> None:
    """The reusable template pack should ship with class, helper, example, and logo."""
    template_dir = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "website"
        / "transcript_templates"
        / "tutranscript"
    )

    assert (template_dir / "tutranscript.cls").is_file()
    assert (template_dir / "tutranscript.sty").is_file()
    assert (template_dir / "tutranscript.el").is_file()
    assert (template_dir / "example.org").is_file()
    assert (template_dir / "logo120pi.png").is_file()
    assert "Clinical" not in (template_dir / "tutranscript.sty").read_text()
    assert "Attmpt Credit" not in (template_dir / "tutranscript.sty").read_text()
    assert "Start Date" not in (template_dir / "tutranscript.sty").read_text()


def test_registrar_transcript_pdf_requires_grade_permission(
    client,
    user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Users without registrar grade permission cannot download transcripts."""
    user = user_factory("registrar_transcript_denied")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="402",
        curriculum_short_name="CURRI_TRANSCRIPT_DENIED",
    )
    student = reg_std_factory("registrar_transcript_denied_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)
    response = client.get(reverse("reg_grade_transcript_pdf", args=[student.id]))

    assert response.status_code == 403


def test_transcript_exports_require_registrar_role_with_grade_permission(
    client,
    user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Grade viewers outside registrar roles cannot export official transcripts."""
    user = user_factory("registrar_transcript_grade_only")
    _grant_grade_view(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="409",
        curriculum_short_name="CURRI_TRANSCRIPT_GRADE_ONLY",
    )
    student = reg_std_factory(
        "registrar_transcript_grade_only_student", curriculum, current
    )
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)

    pdf_response = client.get(reverse("reg_grade_transcript_pdf", args=[student.id]))
    org_response = client.get(reverse("reg_grade_transcript_org", args=[student.id]))
    bulk_response = client.post(
        reverse("reg_grade_transcripts_bulk_pdf"),
        {"student_ids": [str(student.id)]},
    )

    assert pdf_response.status_code == 403
    assert org_response.status_code == 403
    assert bulk_response.status_code == 403


def test_registrar_bulk_transcript_download_exports_selected_students(
    client,
    monkeypatch,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Selected bulk export should include one PDF per checked student."""
    user = reg_user_factory("registrar_transcript_bulk_selected")
    _academic_year, _previous, current = reg_sem_pair_factory()
    first_section, curriculum = reg_sec_factory(
        current,
        course_number="406",
        curriculum_short_name="CURRI_TRANSCRIPT_BULK_SELECTED",
    )
    second_section, _curriculum = reg_sec_factory(
        current,
        course_number="407",
        curriculum_short_name="CURRI_TRANSCRIPT_BULK_SELECTED",
    )
    first_student = reg_std_factory("registrar_bulk_selected_one", curriculum, current)
    second_student = reg_std_factory("registrar_bulk_selected_two", curriculum, current)
    Grade.objects.create(
        student=first_student,
        section=first_section,
        value=_grade_value("a"),
    )
    Grade.objects.create(
        student=second_student,
        section=second_section,
        value=_grade_value("a"),
    )
    seen_layouts: list[str] = []

    def fake_pdf(document, *, layout="portrait_one") -> bytes:
        """Return a small PDF-like payload and record selected layout."""
        seen_layouts.append(layout)
        return f"%PDF {document['student_id']} {layout}".encode()

    monkeypatch.setattr(
        "app.website.views.registrar.render_transcript_document_pdf",
        fake_pdf,
    )

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_transcripts_bulk_pdf"),
        {"student_ids": [str(first_student.id)], "layout": "landscape_two"},
    )
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        payload = archive.read(names[0])

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert len(names) == 1
    assert first_student.student_id in names[0]
    assert "landscape_two" in names[0]
    assert second_student.student_id not in names[0]
    assert seen_layouts == ["landscape_two"]
    assert payload.startswith(b"%PDF")


def test_registrar_bulk_transcript_rejects_empty_selection(
    client,
    reg_user_factory,
) -> None:
    """Bulk export should require explicit checked students."""
    user = reg_user_factory("registrar_transcript_bulk_empty")

    client.force_login(user)
    response = client.post(reverse("reg_grade_transcripts_bulk_pdf"), {})

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("reg_grades_dashboard")


def test_registrar_bulk_transcript_requires_grade_permission(
    client,
    user_factory,
) -> None:
    """Users without registrar grade permission cannot bulk export transcripts."""
    user = user_factory("registrar_transcript_bulk_denied")

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_transcripts_bulk_pdf"),
        {"student_ids": ["1"]},
    )

    assert response.status_code == 403
