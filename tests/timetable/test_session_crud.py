import pytest
from app.timetable.models.session import Session


@pytest.mark.django_db
def test_session_crud(session: Session):
    """CRUD operations for Session."""
    assert Session.objects.filter(pk=session.pk).exists()

    fetched = Session.objects.get(pk=session.pk)
    assert fetched == session

    fetched.room = session.room
    fetched.save()
    updated = Session.objects.get(pk=session.pk)
    assert updated.room == session.room

    updated.delete()
    assert not Session.objects.filter(pk=session.pk).exists()
