"""Test fixtures of the finance app.

Factories return callables for creating additional objects on demand.
"""
# >! TO REVIEW after modification of finance module models
# from __future__ import annotations

# from datetime import date
# from decimal import Decimal
# from typing import Callable, TypeAlias

# import pytest

# from app.finance.models.payment import PaymentMethod
# from app.finance.models import (
#     Payment,
#     Invoice,
#     PaymentHistory,
#     Scholarship,
# )
# from tests.academics.fixture import CurriculumCourseFactory
# from tests.people.fixture import StaffFactory

# PaymentFactory: TypeAlias = Callable[[str, str, Decimal], Payment]
# PaymentFactory: TypeAlias = Callable[[str, str, str, Decimal], Invoice]
# PaymentHistoryFactory: TypeAlias = Callable[
#     [str, str, str, Decimal, Decimal], PaymentHistory
# ]
# ScholarshipFactory: TypeAlias = Callable[[str, str, str, Decimal, date], Scholarship]

# DECIMAL_0 = Decimal("0")
# DECIMAL_1 = Decimal("1")
# DECIMAL_10 = Decimal("10")
# TODAY = date.today()


# @pytest.fixture
# def payment(student) -> Payment:
#     """Default financial record for a student."""

#     return Payment.objects.create(student=student, amount_due=DECIMAL_10)


# @pytest.fixture
# def payment(payment, staff, curriculum_course) -> Invoice:
#     """Default payment record for a curriculum_course."""
#     return Invoice.objects.create(
#         curriculum_course=curriculum_course,
#         amount=DECIMAL_1,
#         method=PaymentMethod.get_default(),
#         recorded_by=staff,
#     )


# @pytest.fixture
# def scholarship(donor, student) -> Scholarship:
#     """Default scholarship linking donor and student."""
#     return Scholarship.objects.create(
#         donor=donor, student=student, amount=DECIMAL_1, start_date=TODAY
#     )


# # ~~~~~~~~~~~~~~~~ Factories ~~~~~~~~~~~~~~~~


# @pytest.fixture
# def payment_factory(student_factory) -> PaymentFactory:
#     """Return a callable to build financial records."""

#     def _make(
#         student_uname: str, curri_short_name: str, amount_due: Decimal = DECIMAL_0
#     ) -> Payment:
#         return Payment.objects.create(
#             student=student_factory(student_uname, curri_short_name),
#             amount_due=amount_due,
#         )

#     return _make


# @pytest.fixture
# def payment_factory(
#     curriculum_course_factory: CurriculumCourseFactory, staff_factory: StaffFactory
# ) -> PaymentFactory:
#     """Return a callable to build payment records."""

#     def _make(
#         course_no: str,
#         curri_short_name: str,
#         staff_uname: str,
#         amount: Decimal = DECIMAL_1,
#     ) -> Invoice:
#         return Invoice.objects.create(
#             curriculum_course=curriculum_course_factory(course_no, curri_short_name),
#             amount=amount,
#             method=PaymentMethod.get_default(),
#             recorded_by=staff_factory(staff_uname),
#         )

#     return _make


# @pytest.fixture
# def scholarship_factory(donor_factory, student_factory) -> ScholarshipFactory:
#     """Return a callable to build scholarships."""

#     def _make(
#         donor_uname: str,
#         student_uname: str,
#         curri_short_name: str = "DFT_CURRI",
#         amount: Decimal = DECIMAL_1,
#         start_date: date = TODAY,
#     ) -> Scholarship:
#         return Scholarship.objects.create(
#             donor=donor_factory(donor_uname),
#             student=student_factory(student_uname, curri_short_name),
#             amount=amount,
#             start_date=start_date,
#         )

#     return _make
