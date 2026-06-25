"""Registrar transcript document regressions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import TypeAlias, cast
from zipfile import ZipFile

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from weasyprint import HTML

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.student import Student
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.transcript_document import build_transcript_document
from app.website.services.transcript_artifacts import (
    load_transcript_artifact,
    transcript_document_with_verification,
)
from app.website.services.transcript_pdf_layout import (
    split_term_groups_for_columns,
    transcript_pdf_layout,
)
from app.website.services.transcript_rendering import (
    render_transcript_document_html,
    render_transcript_document_org,
)
from app.website.services.transcript_types import normalize_transcript_layout

pytestmark = pytest.mark.django_db

RenderedTextT: TypeAlias = tuple[str, float, float]
RenderedPageTextT: TypeAlias = tuple[float, list[RenderedTextT]]

TINIEST_PNG_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO"
    "+/p9sAAAAASUVORK5CYII="
)


def _grade_value(code: str) -> GradeValue:
    """Return a grade value with normalized numeric points."""
    grade_value, _created = GradeValue.objects.get_or_create(code=code)
    return grade_value


def _grant_grade_view(user) -> None:
    """Grant broad grade visibility without registrar role membership."""
    user.user_permissions.add(Permission.objects.get(codename="view_grade"))


def _box_children(box: object) -> list[object]:
    """Return child boxes from a WeasyPrint layout box."""
    raw_children: object = getattr(box, "children", ())
    return list(cast(Iterable[object], raw_children))


def _box_position(box: object, attr: str) -> float:
    """Return a numeric WeasyPrint box coordinate."""
    raw_value: object = getattr(box, attr, 0.0)
    if isinstance(raw_value, int | float):
        return float(raw_value)
    return 0.0


def _rendered_page_texts(html: str) -> list[RenderedPageTextT]:
    """Render transcript HTML and return text boxes grouped by page."""
    project_root = Path(__file__).resolve().parents[2]
    rendered = HTML(string=html, base_url=str(project_root)).render()
    pages: list[RenderedPageTextT] = []
    for raw_page in rendered.pages:
        page = cast(object, raw_page)
        stack: list[object] = [cast(object, getattr(page, "_page_box"))]
        texts: list[RenderedTextT] = []
        while stack:
            box = stack.pop()
            raw_text: object = getattr(box, "text", "")
            if isinstance(raw_text, str) and raw_text:
                texts.append(
                    (
                        raw_text,
                        _box_position(box, "position_x"),
                        _box_position(box, "position_y"),
                    )
                )
            stack.extend(_box_children(box))
        pages.append((_box_position(page, "width"), texts))
    return pages


def _rendered_first_page_texts(html: str) -> RenderedPageTextT:
    """Render transcript HTML and return first-page text boxes."""
    return _rendered_page_texts(html)[0]


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
    monkeypatch,
    settings,
    tmp_path,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar users can download a generated transcript PDF."""
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(
        "app.website.services.transcript_artifacts.qr_code_data_uri",
        lambda _value: TINIEST_PNG_URI,
    )
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
    assert "landscape" in response["Content-Disposition"]
    assert response.content.startswith(b"%PDF")
    assert list((tmp_path / "transcripts" / "manifests").glob("*.json"))

    landscape_response = client.get(
        reverse("reg_grade_transcript_pdf", args=[student.id]),
        {"layout": "portrait"},
    )

    assert landscape_response.status_code == 200
    assert landscape_response["Content-Type"] == "application/pdf"
    assert "landscape" in landscape_response["Content-Disposition"]
    assert landscape_response.content.startswith(b"%PDF")


def test_registrar_transcript_pdf_download_stores_public_verification_artifact(
    client,
    monkeypatch,
    settings,
    tmp_path,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Official transcript downloads should persist a QR-verifiable artifact."""
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(
        "app.website.services.transcript_artifacts.qr_code_data_uri",
        lambda _value: TINIEST_PNG_URI,
    )
    user = reg_user_factory("registrar_transcript_artifact")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="414",
        curriculum_short_name="CURRI_TRANSCRIPT_ARTIFACT",
    )
    student = reg_std_factory(
        "registrar_transcript_artifact_student",
        curriculum,
        current,
    )
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(user)
    response = client.get(
        reverse("reg_grade_transcript_pdf", args=[student.id]),
        {"layout": "landscape"},
    )
    manifest_paths = list((tmp_path / "transcripts" / "manifests").glob("*.json"))
    assert response.status_code == 200
    assert len(manifest_paths) == 1

    artifact = load_transcript_artifact(manifest_paths[0].stem)
    transcript = build_transcript_document(student.id)
    pdf_path = tmp_path / artifact["pdf_relative_path"]
    verify_path = reverse("transcript_verify", args=[artifact["token"]])
    verify_pdf_path = reverse("transcript_verify_pdf", args=[artifact["token"]])

    assert artifact["layout"] == "landscape"
    assert artifact["student_id"] == student.student_id
    assert artifact["student_name"] == transcript["student_name"]
    assert artifact["verification_url"].endswith(verify_path)
    assert pdf_path.read_bytes() == response.content

    verify_response = client.get(verify_path)
    verify_content = verify_response.content.decode()
    assert verify_response.status_code == 200
    assert student.student_id in verify_content
    assert artifact["token"] in verify_content

    pdf_response = client.get(verify_pdf_path)
    assert pdf_response.status_code == 200
    assert pdf_response["Content-Type"] == "application/pdf"
    assert b"".join(pdf_response.streaming_content) == response.content


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
    current.start_date = date(2026, 3, 4)
    current.end_date = date(2026, 5, 6)
    current.save(update_fields=["start_date", "end_date"])
    section.start_date = date(2026, 3, 4)
    section.end_date = date(2026, 5, 6)
    section.save(update_fields=["start_date", "end_date"])
    student = reg_std_factory("registrar_transcript_html_student", curriculum, current)
    student.physical_address = "Hoffman Station, Harper City\nMaryland County, Liberia"
    student.birth_date = date(1982, 5, 17)
    student.save(update_fields=["physical_address", "birth_date"])
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    html = render_transcript_document_html(document, layout="landscape")

    assert document["enrollment_date"] == "Mar 4, 2026"
    assert document["completion_date"] == "May 6, 2026"
    assert document["graduation_date"] == "N/A"
    assert "Curri:" in html
    assert "<strong>Enrol:</strong> Mar 4, 2026" in html
    assert "<strong>Comp:</strong> May 6, 2026" in html
    assert "<strong>Grad:</strong> N/A" in html
    assert "Curriculum:" not in html
    assert "Enrollment:" not in html
    assert "Completion:" not in html
    assert "Graduation:" not in html
    assert "March 4, 2026" not in html
    assert "May 6, 2026" in html
    assert "@bottom-center" in html
    assert "Registrar: __________________" in html
    assert "Date: __________________" in html
    assert "Printed on" not in html
    assert "Clinical" not in html
    assert "Attmpt Credit" not in html
    assert "Start Date" not in html
    assert "End Date" not in html
    assert "Attempted<br/>Credit" not in html
    assert 'class="institution-identity"' in html
    assert 'class="document-title"' in html
    assert 'class="student-meta"' in html
    assert 'data-transcript-layout="landscape"' in html
    assert 'class="layout-landscape pdf-layout-landscape-two"' in html
    assert "size: A4 landscape;" in html
    assert 'class="summary-strip"' in html
    assert 'class="institution-identity-table"' in html
    assert 'class="summary-cell summary-cell--program"' in html
    assert ".summary-cell--program {\n        width: 35%;" in html
    assert ".summary-cell--college {\n        width: 21.5%;" in html
    assert 'class="detail-columns-table"' in html
    assert 'class="detail-columns"' not in html
    assert ".detail-columns {" not in html
    assert "display: grid" not in html
    assert "grid-template" not in html
    assert ".course-line {\n        display: grid;" not in html
    assert ".course-line {\n        white-space: nowrap;" in html
    assert "<th>Grade</th>" in html
    assert "<th>Att.</th>" in html
    assert "<th>Earned</th>" in html
    assert "<th>Pts</th>" in html
    assert "font-size: 8pt;" in html
    assert "font-size: 9pt;" not in html
    assert "padding-right: 5mm;" in html
    assert "padding-left: 5mm;" in html
    assert "border-left: 0.2mm solid #111;" in html
    assert "width: 30mm;" not in html
    assert "Transcript Summary" not in html
    assert 'class="summary-metrics"' not in html
    assert 'class="totals-table summary-totals"' not in html
    assert "04/03/26" not in html
    assert "06/05/26" not in html
    assert "Maryland County, Republic of Liberia" in html
    assert "www.Tubmanu.edu.lr &middot; registrar@tubmanu.edu.lr" in html
    assert html.count("Maryland County, Liberia") == 1
    assert "Transcript Back Matter" in html
    assert "break-before: left" in html
    assert "Grade Letters and Credit Points" in html
    assert "Mention and honor thresholds" not in html
    assert "Online transcript verification link" not in html


def test_transcript_pdf_html_includes_qr_metadata_for_verified_artifact(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Issued transcript documents should render visible QR verification metadata."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="415",
        curriculum_short_name="CURRI_TRANSCRIPT_QR",
    )
    student = reg_std_factory("registrar_transcript_qr_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))
    document = build_transcript_document(student.id)
    verified_document = transcript_document_with_verification(
        document,
        qr_code_uri=TINIEST_PNG_URI,
        token="qr-token-1",
        verification_url="https://tusis.koba.sarl/transcripts/verify/qr-token-1/",
    )

    html = render_transcript_document_html(verified_document, layout="landscape")

    assert "Scan to verify transcript." in html
    assert "Token: qr-token-1" in html
    assert "https://tusis.koba.sarl/transcripts/verify/qr-token-1/" in html
    assert 'class="verification-qr-cell"' in html
    assert "width: 22mm;" in html
    assert "height: 20mm;" in html
    assert "width: 20mm;" in html
    assert TINIEST_PNG_URI in html
    assert html.index('class="back-matter"') < html.index('class="verification-block"')
    assert html.index("***CONCLUSION OF TRANSCRIPT***") < html.index(
        'class="back-matter"'
    )


def test_verified_landscape_pdf_renders_long_transcript_without_grid_crash(
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Long verified landscape transcripts should avoid WeasyPrint grid asserts."""
    semesters: list[Semester] = []
    for year_offset in range(6):
        start_year = 2017 + year_offset
        academic_year = AcademicYear.objects.create(start_date=date(start_year, 8, 1))
        semester_one = Semester.objects.create(
            academic_year=academic_year,
            number=1,
            start_date=date(start_year, 9, 1),
        )
        semesters.append(semester_one)
        if len(semesters) == 11:
            break
        semester_two = Semester.objects.create(
            academic_year=academic_year,
            number=2,
            start_date=date(start_year + 1, 1, 15),
        )
        semesters.append(semester_two)
        if len(semesters) == 11:
            break

    sections: list[Section] = []
    curriculum: Curriculum | None = None
    for semester_index, semester in enumerate(semesters):
        for course_index in range(6):
            section, curriculum = reg_sec_factory(
                semester,
                course_number=str(700 + semester_index * 6 + course_index),
                curriculum_short_name="CURRI_TRANSCRIPT_LONG_VERIFIED",
            )
            course = section.curriculum_course.course
            course.title = (
                f"Long Verified Transcript Course {semester_index + 1}-{course_index + 1}"
            )
            course.save(update_fields=["title"])
            sections.append(section)
    assert curriculum is not None

    student = reg_std_factory(
        "registrar_transcript_long_verified_student",
        curriculum,
        semesters[0],
    )
    for section in sections:
        Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    verified_document = transcript_document_with_verification(
        document,
        qr_code_uri=TINIEST_PNG_URI,
        token="long-token-1",
        verification_url="https://tusis.koba.sarl/transcripts/verify/long-token-1/",
    )
    html = render_transcript_document_html(verified_document, layout="landscape")
    project_root = Path(__file__).resolve().parents[2]
    pdf_bytes = HTML(string=html, base_url=str(project_root)).write_pdf()

    assert len(document["term_groups"]) == 11
    assert sum(len(group["rows"]) for group in document["term_groups"]) == 66
    assert bytes(pdf_bytes).startswith(b"%PDF")


def test_landscape_pdf_render_keeps_transcript_rows_visible(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Landscape PDF rendering should keep course rows visible on page one."""
    academic_year, first, second = reg_sem_pair_factory(
        date(2026, 6, 20),
        previous_offset_days=300,
        current_offset_days=220,
    )
    third = Semester.objects.create(
        academic_year=academic_year,
        number=3,
        start_date=date(2026, 2, 1),
    )
    fourth = Semester.objects.create(
        academic_year=academic_year,
        number=4,
        start_date=date(2026, 5, 1),
    )
    curriculum_name = "CURRI_TRANSCRIPT_RENDER"
    sections: list[Section] = []
    curriculum: Curriculum | None = None
    for index, semester in enumerate([first, second, third, fourth]):
        section, curriculum = reg_sec_factory(
            semester,
            course_number=str(510 + index),
            curriculum_short_name=curriculum_name,
        )
        course = section.curriculum_course.course
        course.title = f"Landscape Sentinel {index + 1}"
        course.save(update_fields=["title"])
        sections.append(section)
    assert curriculum is not None
    student = reg_std_factory("registrar_transcript_render_student", curriculum, first)
    for section in sections:
        Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    pdf_layout = transcript_pdf_layout("landscape", document["term_groups"])
    left_code = pdf_layout["term_columns"][0][0]["rows"][0]["course_code"]
    right_code = pdf_layout["term_columns"][1][0]["rows"][0]["course_code"]
    html = render_transcript_document_html(document, layout="landscape")
    page_width, texts = _rendered_first_page_texts(html)
    positions = {text: (x, y) for text, x, y in texts}

    assert left_code in positions
    assert right_code in positions
    assert 0 < positions[left_code][0] < page_width / 2
    assert page_width / 2 < positions[right_code][0] < page_width
    assert "Transcript Back Matter" not in {text for text, _x, _y in texts}


def test_landscape_pdf_keeps_expected_max_record_on_first_page(
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Expected maximum transcripts should remain readable on the first page."""
    semesters: list[Semester] = []
    for index in range(10):
        academic_year = AcademicYear.objects.create(start_date=date(2016 + index, 8, 1))
        semesters.append(
            Semester.objects.create(
                academic_year=academic_year,
                number=1,
                start_date=date(2016 + index, 9, 1),
            )
        )

    sections: list[Section] = []
    curriculum: Curriculum | None = None
    for semester_index, semester in enumerate(semesters):
        for course_index in range(5):
            section, curriculum = reg_sec_factory(
                semester,
                course_number=str(800 + semester_index * 5 + course_index),
                curriculum_short_name="CURRI_TRANSCRIPT_EXPECTED_MAX",
            )
            course = section.curriculum_course.course
            course.title = f"Expected Max Transcript Course {semester_index + 1}"
            course.save(update_fields=["title"])
            sections.append(section)
    assert curriculum is not None

    student = reg_std_factory(
        "registrar_transcript_expected_max_student",
        curriculum,
        semesters[0],
    )
    for section in sections:
        Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    document = build_transcript_document(student.id)
    verified_document = transcript_document_with_verification(
        document,
        qr_code_uri=TINIEST_PNG_URI,
        token="expected-max-token-1",
        verification_url="https://tusis.koba.sarl/transcripts/verify/expected-max/",
    )
    html = render_transcript_document_html(verified_document, layout="landscape")
    first_page_texts = {text for text, _x, _y in _rendered_page_texts(html)[0][1]}
    course_codes = {
        row["course_code"] for group in document["term_groups"] for row in group["rows"]
    }

    assert len(document["term_groups"]) == 10
    assert sum(len(group["rows"]) for group in document["term_groups"]) == 50
    assert course_codes <= first_page_texts
    assert any("CONCLUSION" in text for text in first_page_texts)
    assert "Transcript Back Matter" not in first_page_texts


def test_transcript_pdf_layout_splits_terms_without_breaking_semesters(
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """The web PDF layout should balance whole semester blocks into two columns."""
    _academic_year, previous, current = reg_sem_pair_factory()
    first_section, curriculum = reg_sec_factory(
        previous,
        course_number="410",
        curriculum_short_name="CURRI_TRANSCRIPT_COLUMNS",
    )
    second_section, _curriculum = reg_sec_factory(
        current,
        course_number="411",
        curriculum_short_name="CURRI_TRANSCRIPT_COLUMNS",
    )
    student = reg_std_factory(
        "registrar_transcript_columns_student", curriculum, previous
    )
    Grade.objects.create(student=student, section=first_section, value=_grade_value("a"))
    Grade.objects.create(student=student, section=second_section, value=_grade_value("b"))

    document = build_transcript_document(student.id)
    columns = split_term_groups_for_columns(document["term_groups"])
    flattened_labels = [group["term_label"] for column in columns for group in column]
    pdf_layout = transcript_pdf_layout("portrait", document["term_groups"])

    assert len(columns) == 2
    assert all(columns)
    assert flattened_labels == [group["term_label"] for group in document["term_groups"]]
    assert pdf_layout["term_columns"] == columns
    assert pdf_layout["grade_label"] == "Gr."


def test_transcript_layout_normalization_accepts_legacy_values() -> None:
    """Legacy transcript layout query values should map to current choices."""
    assert normalize_transcript_layout("portrait_one") == "portrait"
    assert normalize_transcript_layout("portrait_two") == "portrait"
    assert normalize_transcript_layout("landscape_two") == "landscape"
    assert normalize_transcript_layout("landscape") == "landscape"


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


def test_registrar_transcript_page_shows_pdf_download_action_only(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """The transcript preview should expose PDF download without visible Org source."""
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
    assert "Transcript export" in content
    assert "data-transcript-layout-select" not in content
    assert "Portrait" not in content
    assert "Landscape" not in content
    assert "Download official transcript" in content
    assert "data-transcript-pdf-download" in content
    assert "Download Org source" not in content
    assert "data-transcript-org-download" not in content


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
    style_source = (template_dir / "tutranscript.sty").read_text()
    assert "Clinical" not in style_source
    assert "Attmpt Credit" not in style_source
    assert "Start Date" not in style_source
    assert "Registrar: " in style_source
    assert r"\TUTranscriptClearToEvenPage" in style_source


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

    def fake_issue(request, *, layout="portrait", student_id: int):
        """Return a small artifact-like payload and record selected layout."""
        seen_layouts.append(layout)
        student = Student.objects.get(id=student_id)
        return SimpleNamespace(
            filename=f"transcript_{student.student_id}_{layout}_mock.pdf",
            pdf_bytes=f"%PDF {student.student_id} {layout}".encode(),
        )

    monkeypatch.setattr(
        "app.website.views.registrar.issue_transcript_artifact",
        fake_issue,
    )

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_transcripts_bulk_pdf"),
        {"student_ids": [str(first_student.id)], "layout": "portrait"},
    )
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        payload = archive.read(names[0])

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert len(names) == 1
    assert first_student.student_id in names[0]
    assert "landscape" in names[0]
    assert second_student.student_id not in names[0]
    assert seen_layouts == ["landscape"]
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
