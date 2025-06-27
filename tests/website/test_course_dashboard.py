"""Tests for the course dashboard view."""

import pytest
from django.urls import reverse

from app.registry.models.registration import Registration
from app.registry.choices import StatusRegistration
from app.shared.status import StatusHistory
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from app.timetable.models.section import Section
from app.academics.models.program import Program
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum


@pytest.mark.django_db
def test_course_dashboard_add_update_remove(client, student, semester):
    """Student can add, update, and remove a registration."""
    curriculum = Curriculum.get_default()
    course = Course.objects.create(number="999", title="Test Course")
    program = Program.objects.create(curriculum=curriculum, course=course)
    section = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
        max_seats=30,
    )

    url = reverse("course_dashboard")

    client.force_login(student.user)

    # add registration
    response = client.post(url, {"action": "add", "section_id": section.id})
    assert response.status_code == 302
    reg = Registration.objects.get(student=student, section=section)

    # update registration
    response = client.post(
        url,
        {
            "action": "update",
            "registration_id": reg.id,
            "status": reg.status,
        },
    )
    assert response.status_code == 302

    # remove registration
    response = client.post(
        url,
        {"action": "remove", "registration_id": reg.id},
    )
    assert response.status_code == 302
    assert Registration.objects.filter(pk=reg.id).count() == 0

    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table in tables:
        ct = ContentType.objects.get_for_model(Registration)
        history_exists = StatusHistory.objects.filter(
            content_type=ct, object_id=reg.id, status=StatusRegistration.REMOVE
        ).exists()
        assert history_exists
