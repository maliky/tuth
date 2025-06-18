import pytest
from datetime import time
from django.core.exceptions import ValidationError

from app.timetable.models.session import Schedule, Session
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_session_overlap_same_room_raises_validationerror(room, course, semester):
    sched1 = Schedule.objects.create(
        weekday=1, start_time=time(8, 0), end_time=time(9, 0)
    )
    sched2 = Schedule.objects.create(
        weekday=1, start_time=time(8, 30), end_time=time(9, 30)
    )

    sec1 = Section.objects.create(course=course, semester=semester, number=1)
    sec2 = Section.objects.create(course=course, semester=semester, number=2)

    Session.objects.create(room=room, schedule=sched1, section=sec1)
    sess = Session(room=room, schedule=sched2, section=sec2)

    with pytest.raises(ValidationError):
        sess.clean()


@pytest.mark.django_db
def test_session_non_overlap_same_room_passes(room, course, semester):
    sched1 = Schedule.objects.create(
        weekday=1, start_time=time(8, 0), end_time=time(9, 0)
    )
    sched2 = Schedule.objects.create(
        weekday=1, start_time=time(9, 0), end_time=time(10, 0)
    )

    sec1 = Section.objects.create(course=course, semester=semester, number=1)
    sec2 = Section.objects.create(course=course, semester=semester, number=2)

    Session.objects.create(room=room, schedule=sched1, section=sec1)
    sess = Session(room=room, schedule=sched2, section=sec2)

    sess.clean()
