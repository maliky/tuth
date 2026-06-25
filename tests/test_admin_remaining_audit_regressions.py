"""Regression tests for remaining admin click-audit findings."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from impersonate.models import ImpersonationLog

from app.academics.admin.inlines import CurriCrsIL
from app.academics.models import Course, CurriCrs, Curriculum, Department
from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db


def _login_admin(client, superuser) -> None:
    """Authenticate the test client as a superuser."""
    client.force_login(superuser)


def _assert_ok(response) -> None:
    """Assert that an admin GET rendered successfully."""
    assert response.status_code == 200, response.content[:500]


def _admin_request(superuser):
    """Return a request object suitable for direct ModelAdmin calls."""
    request = RequestFactory().get("/admin/")
    request.user = superuser
    return request


def test_impersonation_log_admin_exposes_no_add_link(client, superuser) -> None:
    """Read-only impersonation logs should not expose an Add affordance."""
    _login_admin(client, superuser)
    model_admin = admin.site._registry[ImpersonationLog]
    request = _admin_request(superuser)

    assert not model_admin.has_add_permission(request)

    response = client.get(reverse("admin:impersonate_impersonationlog_changelist"))
    _assert_ok(response)
    content = response.content
    assert b"/admin/impersonate/impersonationlog/add/" not in content

    add_response = client.get(reverse("admin:impersonate_impersonationlog_add"))
    assert add_response.status_code == 403


def test_registration_admin_uses_resilient_jquery_loader(client, superuser) -> None:
    """Registration admin JS should not assume immediate global jQuery availability."""
    _login_admin(client, superuser)
    RegistrationStatus._populate_attributes_and_db()

    response = client.get(reverse("admin:registry_registration_add"))
    _assert_ok(response)
    assert b"build/registry/static/registry/js/registration_admin.js" in response.content

    source = Path("app/registry/static/registry/js/registration_admin.ts").read_text()
    assert "runWhenAdminJQueryIsReady(initRegistrationAdmin, 20)" in source
    assert "})(django.jQuery)" not in source


def test_registration_admin_searches_student_and_course_section(
    client,
    superuser,
    semester,
) -> None:
    """Registration admin search should match registrar-facing student and course keys."""
    _login_admin(client, superuser)
    RegistrationStatus._populate_attributes_and_db()
    curriculum = Curriculum.get_dft("CURRI_REG_ADMIN_SEARCH")
    department = Department.get_dft("ENVS")
    target_course = Course.objects.create(
        department=department,
        number="208",
        title="Environmental Systems",
    )
    other_course = Course.objects.create(
        department=Department.get_dft("BIOL"),
        number="110",
        title="Biology Orientation",
    )
    target_section = Section.objects.create(
        semester=semester,
        curriculum_course=CurriCrs.objects.create(
            curriculum=curriculum,
            course=target_course,
        ),
        number=1,
    )
    other_section = Section.objects.create(
        semester=semester,
        curriculum_course=CurriCrs.objects.create(
            curriculum=curriculum,
            course=other_course,
        ),
        number=2,
    )
    target_student = Student.objects.create(
        username="anthonyk.tchouin",
        first_name="Anthony",
        last_name="Tchouin",
        student_id="TU-31625",
        last_enrolled_semester=semester,
    )
    target_student.long_name = "Anthony Klakur Tchouin"
    target_student.save(update_fields=["long_name"])
    other_student = Student.objects.create(
        username="other.student",
        first_name="Other",
        last_name="Student",
        student_id="TU-99999",
        last_enrolled_semester=semester,
    )
    target_registration = Registration.objects.create(
        student=target_student,
        section=target_section,
    )
    other_registration = Registration.objects.create(
        student=other_student,
        section=other_section,
    )
    changelist_url = reverse("admin:registry_registration_changelist")

    for query in (
        "31625",
        "Anthony",
        "Tchouin",
        "anthonyk.tchouin",
        "ENVS208",
        "Environmental",
        "ENVS208 1",
    ):
        response = client.get(changelist_url, {"q": query})
        _assert_ok(response)
        result_ids = {
            registration.id for registration in response.context["cl"].result_list
        }
        assert target_registration.id in result_ids
        assert other_registration.id not in result_ids

    response = client.get(changelist_url)
    _assert_ok(response)
    content = response.content.decode()
    assert "Registration" in content
    assert "Section code" in content
    assert "Student" in content
    assert str(target_section.semester) in content
    assert f"{target_section.short_code} - {target_student}" in content

    for params in (
        {"student": str(target_student.id)},
        {"section": str(target_section.id)},
    ):
        response = client.get(changelist_url, params)
        _assert_ok(response)
        result_ids = {
            registration.id for registration in response.context["cl"].result_list
        }
        assert target_registration.id in result_ids
        assert other_registration.id not in result_ids

    section_admin = admin.site._registry[Section]
    request = _admin_request(superuser)
    section_qs = section_admin.get_queryset(request)
    for section_code in ("ENVS208:s1", "ENVS208 1", "ENVS208-s1"):
        result_qs, _use_distinct = section_admin.get_search_results(
            request,
            section_qs,
            section_code,
        )
        assert target_section.id in set(result_qs.values_list("id", flat=True))
        assert other_section.id not in set(result_qs.values_list("id", flat=True))


def test_student_semester_invoice_add_omits_existing_row_inlines(
    superuser, student, semester
) -> None:
    """Invoice add screens should skip detail inlines until the parent is saved."""
    InvoiceStatus._populate_attributes_and_db()
    Payer._populate_attributes_and_db()
    model_admin = admin.site._registry[StdSemesterInvoice]
    request = _admin_request(superuser)

    assert model_admin.get_inline_instances(request, obj=None) == []

    invoice = StdSemesterInvoice.objects.create(student=student, semester=semester)
    inline_instances = model_admin.get_inline_instances(request, obj=invoice)
    assert len(inline_instances) == 2


def test_scoped_admins_use_responsive_page_sizes() -> None:
    """Audited high-volume admin pages should avoid very large default pages."""
    assert admin.site._registry[Course].list_per_page == 50
    assert admin.site._registry[Course].list_max_show_all == 200
    assert admin.site._registry[Student].list_per_page == 50
    assert admin.site._registry[StdSemesterInvoice].list_per_page == 50


def test_curriculum_course_inline_avoids_unused_registration_count(
    superuser,
) -> None:
    """Curriculum inline grouping should not join registrations for unused counts."""
    inline = CurriCrsIL(Curriculum, admin.site)
    queryset = inline.get_queryset(_admin_request(superuser))
    query_sql = str(queryset.query)

    assert "section_registrations" not in query_sql
    assert queryset.query.select_related


def test_audited_slow_admin_pages_still_load(
    client, superuser, curriculum_course, student
) -> None:
    """The optimized admin pages should continue to render successfully."""
    _login_admin(client, superuser)
    InvoiceStatus._populate_attributes_and_db()
    Payer._populate_attributes_and_db()

    urls = [
        reverse("admin:finance_stdsemesterinvoice_add"),
        reverse("admin:academics_course_changelist"),
        reverse("admin:people_student_changelist"),
        reverse(
            "admin:academics_curriculum_change",
            args=[curriculum_course.curriculum_id],
        ),
    ]

    for url in urls:
        _assert_ok(client.get(url))
