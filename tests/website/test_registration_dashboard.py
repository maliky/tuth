"""Tests for the registration dashboard view."""

import pytest
from django.urls import reverse

from app.registry.models.registration import Registration
from app.registry.choices import StatusRegistration
from app.timetable.models.section import Section
from app.academics.models.program import Program
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum


@pytest.mark.django_db
def test_registration_dashboard_reserve_cancel(client, student, semester):
    """Student can reserve and cancel a section."""
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

    url = reverse("registration_dashboard")

    client.force_login(student.user)

    response = client.post(url, {"action": "reserve", "sections": [section.id]})
    assert response.status_code == 302
    reg = Registration.objects.get(student=student, section=section)
    assert reg.status == StatusRegistration.PENDING

    response = client.post(url, {"action": "cancel", "sections": [section.id]})
    assert response.status_code == 302
    assert not Registration.objects.filter(pk=reg.id).exists()
