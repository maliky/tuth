from __future__ import annotations

from typing import Iterable, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from app.people.models import StudentProfile
from app.shared.constants import MAX_STUDENT_CREDITS
from app.shared.constants.finance import StatusReservation
from app.timetable.models import Reservation, Section


def reserve_sections(
    student: StudentProfile, sections: Iterable[Section]
) -> List[Reservation]:
    """Create reservation objects for ``student`` on each section.

    All checks are performed beforehand so the operation is atomic.
    """
    section_list = list(sections)

    with transaction.atomic():
        # > detail what is the output of the assignement below.
        current = (
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
        prospective = current + new_credits
        # > this will need to be updated.
        # > the logic is that student can request a course even is credit is above
        # > MAX_STUDENT_CREDIT but, the dean and VPAA can still validate
        # > the reservation.  So their should be a temporary state, flag for
        # > dean and VPAA
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
            )
            reservations.append(res)
        return reservations
