from datetime import datetime, date
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from app.finance.admin.core import FinancialRecordAdmin, PaymentHistoryAdmin
from app.finance.models import FinancialRecord, PaymentHistory
from app.people.choices import UserRole
from app.people.models.role_assignment import RoleAssignment
from app.people.models.student import Student
from app.registry.admin.core import GradeAdmin, RegistrationAdmin
from app.registry.models import Grade, Registration
from app.timetable.models.section import Section
from app.academics.models.program import Program


@pytest.fixture
def registrar(user_factory):
    user = user_factory("reg_user")
    RoleAssignment.objects.create(
        user=user, role=UserRole.REGISTRAR, start_date=date.today()
    )
    return user


@pytest.fixture
def financial_officer(user_factory):
    user = user_factory("fin_user")
    RoleAssignment.objects.create(
        user=user, role=UserRole.FINANCIALOFFICER, start_date=date.today()
    )
    return user


@pytest.fixture
def basic_user(user_factory, curriculum, semester):
    user = user_factory("plain")
    Student.objects.create(
        user=user, curriculum=curriculum, current_enroled_semester=semester
    )
    return user


@pytest.fixture
def setup_records(semester_factory, curriculum_factory, course_factory, user_factory, staff):
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

    Grade.objects.create(
        student=stud_current, section=sec_current, letter_grade="A", numeric_grade=90
    )
    Grade.objects.create(
        student=stud_past, section=sec_past, letter_grade="B", numeric_grade=80
    )

    Registration.objects.create(student=stud_current, section=sec_current)
    Registration.objects.create(student=stud_past, section=sec_past)

    fr_current = FinancialRecord.objects.create(student=stud_current, total_due=Decimal("0"))
    fr_past = FinancialRecord.objects.create(student=stud_past, total_due=Decimal("0"))

    PaymentHistory.objects.create(financial_record=fr_current, amount=Decimal("1"), recorded_by=staff)
    PaymentHistory.objects.create(financial_record=fr_past, amount=Decimal("1"), recorded_by=staff)

    return current_sem, past_sem


@pytest.mark.django_db
def test_historical_access_mixin(registrar, financial_officer, basic_user, setup_records):
    rf = RequestFactory()
    site = AdminSite()

    grade_admin = GradeAdmin(Grade, site)
    reg_admin = RegistrationAdmin(Registration, site)
    fr_admin = FinancialRecordAdmin(FinancialRecord, site)
    ph_admin = PaymentHistoryAdmin(PaymentHistory, site)

    req_registrar = rf.get("/")
    req_registrar.user = registrar

    req_fin = rf.get("/")
    req_fin.user = financial_officer

    req_plain = rf.get("/")
    req_plain.user = basic_user

    assert grade_admin.get_queryset(req_registrar).count() == 2
    assert reg_admin.get_queryset(req_registrar).count() == 2
    assert fr_admin.get_queryset(req_fin).count() == 2
    assert ph_admin.get_queryset(req_fin).count() == 2

    assert grade_admin.get_queryset(req_plain).count() == 1
    assert reg_admin.get_queryset(req_plain).count() == 0
    assert fr_admin.get_queryset(req_plain).count() == 1
    assert ph_admin.get_queryset(req_plain).count() == 1
