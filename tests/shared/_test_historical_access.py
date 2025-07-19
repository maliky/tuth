"""Test for historical Access?  Needs clarifications."""

from datetime import datetime, date
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from app.finance.admin.core import FinancialRecordAdmin, PaymentHistoryAdmin
from app.finance.models import FinancialRecord, PaymentHistory
from app.people.models.student import Student
from app.registry.admin.core import GradeAdmin, RegistrationAdmin
from app.registry.models import Grade, GradeType, Registration
from app.timetable.models.section import Section
from app.academics.models.program import Program


@pytest.fixture
def setup_records(
    semester_factory, curriculum_factory, course_factory, user_factory, staff
):
    current_sem = semester_factory(1, datetime(2025, 9, 1))
    past_sem = semester_factory(1, datetime(2024, 9, 1))
    current_sem.start_date = date(2025, 9, 1)
    past_sem.start_date = date(2024, 9, 1)
    current_sem.save()
    past_sem.save()

    curriculum = curriculum_factory("CURR")
    course = course_factory("101")
    program = Program.objects.create(curriculum=curriculum, course=course)

    sec_current = Section.objects.create(program=program, semester=current_sem)
    sec_past = Section.objects.create(program=program, semester=past_sem)

    stud_current = Student.objects.create(
        user=user_factory("stud_new"),
        curriculum=curriculum,
        current_enroled_semester=current_sem,
    )
    stud_past = Student.objects.create(
        user=user_factory("stud_old"),
        curriculum=curriculum,
        current_enroled_semester=past_sem,
    )

    grade_a = GradeType.objects.create(code="A")
    grade_b = GradeType.objects.create(code="B")
    Grade.objects.create(student=stud_current, section=sec_current, grade=grade_a)
    Grade.objects.create(student=stud_past, section=sec_past, grade=grade_b)

    Registration.objects.create(student=stud_current, section=sec_current)
    Registration.objects.create(student=stud_past, section=sec_past)

    fr_current = FinancialRecord.objects.create(
        student=stud_current, total_due=Decimal("0")
    )
    fr_past = FinancialRecord.objects.create(student=stud_past, total_due=Decimal("0"))

    PaymentHistory.objects.create(
        financial_record=fr_current, amount=Decimal("1"), recorded_by=staff
    )
    PaymentHistory.objects.create(
        financial_record=fr_past, amount=Decimal("1"), recorded_by=staff
    )

    return current_sem, past_sem


@pytest.mark.django_db
def test_historical_access_mixin(
    finance_officer, registrar_officer, student, setup_records
):
    """Test the access to the history?"""

    # > should setup_records be used ?
    req_factory = RequestFactory()
    admin_site = AdminSite()

    grade_admin = GradeAdmin(Grade, admin_site)
    reg_admin = RegistrationAdmin(Registration, admin_site)
    fr_admin = FinancialRecordAdmin(FinancialRecord, admin_site)
    ph_admin = PaymentHistoryAdmin(PaymentHistory, admin_site)

    # > what is req_factory.get ?
    req_registrar = req_factory.get("/")
    req_registrar.user = registrar_officer

    # > We do it 3 times to get different things ?
    req_fin = req_factory.get("/")
    req_fin.user = finance_officer

    req_plain = req_factory.get("/")
    req_plain.user = student

    # > What we assert is not clear.  Need more comments on prerequisite
    # > for this tests to work.
    assert grade_admin.get_queryset(req_registrar).count() == 2
    assert reg_admin.get_queryset(req_registrar).count() == 2
    assert fr_admin.get_queryset(req_fin).count() == 2
    assert ph_admin.get_queryset(req_fin).count() == 2

    assert grade_admin.get_queryset(req_plain).count() == 1
    assert reg_admin.get_queryset(req_plain).count() == 0
    assert fr_admin.get_queryset(req_plain).count() == 1
    assert ph_admin.get_queryset(req_plain).count() == 1
