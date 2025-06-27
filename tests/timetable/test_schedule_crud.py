import pytest
from datetime import datetime
from app.timetable.models.schedule import Schedule


@pytest.mark.django_db
def test_schedule_crud():
    """CRUD operations for Schedule."""
    now = datetime.now().time()
    schedule = Schedule.objects.create(weekday=1, start_time=now)
    assert Schedule.objects.filter(pk=schedule.pk).exists()

    fetched = Schedule.objects.get(pk=schedule.pk)
    assert fetched == schedule

    fetched.end_time = now
    fetched.save()
    updated = Schedule.objects.get(pk=schedule.pk)
    assert updated.end_time == now

    updated.delete()
    assert not Schedule.objects.filter(pk=schedule.pk).exists()
