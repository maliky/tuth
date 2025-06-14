"""Business logic helpers for the timetable app."""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from app.people.models import Student
from app.shared.constants import MAX_STUDENT_CREDITS, StatusReservation
from app.timetable.models import Reservation, Section


def reserve_sections(student: Student, sections: Iterable[Section]) -> List[Reservation]:
    """Reserve a set of sections for a student.

    Parameters
    ----------
    student : Student
        The student requesting the reservations.
    sections : Iterable[Section]
        Sections to be reserved.

    Returns
    -------
    list[Reservation]
        The newly created reservation objects.

    Raises
    ------
    ValidationError
        If capacity or credit constraints are violated.
    """
    section_list = list(sections)

    with transaction.atomic():
        # > detail what is the output of the assignement below.
        current_reservations = (
            Reservation.objects.filter(
                student=student,
                status__in=[
                    StatusReservation.REQUESTED,
                    StatusReservation.VALIDATED,
                ],
            ).aggregate(total=Sum("section__course__credit_hours"))["total"]
            or 0
        )

        # > I hope to come here only with available section, as
        # > only the section with available seats should be shown to the student
        for sec in section_list:
            if not sec.has_available_seats():
                raise ValidationError(f"Section {sec} has no available seats.")

        new_credits = sum(sec.course.credit_hours for sec in section_list)
        prospective = current_reservations + new_credits
        # > this will need to be updated.
        # > the logic is that student cannot request a course even his credit is
        # > above MAX_STUDENT_CREDIT but, the dean and VPAA can still authorise
        # > such reservation to be made.  So their should be a temporary state,
        # > flag for dean and VPAA
        if prospective > MAX_STUDENT_CREDITS:
            raise ValidationError(
                f"Credit limit exceeded ({prospective}/{MAX_STUDENT_CREDITS})."
            )

        reservations: List[Reservation] = []

        for sec in section_list:
            res = Reservation.objects.create(
                student=student,
                section=sec,
                status=StatusReservation.REQUESTED,
                validation_deadline=timezone.now() + timedelta(days=2),
            )
            Section.objects.filter(pk=sec.pk).update(
                current_registrations=F("current_registrations") + 1
            )
            reservations.append(res)
        return reservations
