"""Regression tests for remaining admin click-audit findings."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from impersonate.models import ImpersonationLog

from app.academics.admin.inlines import CurriCrsIL
from app.academics.models import Course, Curriculum
from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.people.models.student import Student
from app.registry.models.status_types import RegistrationStatus

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
