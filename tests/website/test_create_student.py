"""Tests for the create_student view."""

import pytest
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from app.shared.auth.perms import UserRole
from app.people.models.student import Student


@pytest.mark.django_db
def test_enrollment_officer_can_create_student(
    client, role_user_factory, curriculum, semester
):
    """Enrollment officers can access the form and create a student."""
    officer = role_user_factory(UserRole.ENROLLMENT_OFFICER)
    ct = ContentType.objects.get_for_model(Student)
    perm = Permission.objects.get(codename="add_student", content_type=ct)
    officer.groups.first().permissions.add(perm)

    client.force_login(officer)
    url = reverse("create_student")

    response = client.get(url)
    assert response.status_code == 200

    data = {
        "first_name": "Alice",
        "last_name": "Smith",
        "curriculum": curriculum.id,
        "current_enrolled_semester": semester.id,
    }

    response = client.post(url, data)
    assert response.status_code == 302
    assert Student.objects.filter(
        user__first_name="Alice", user__last_name="Smith"
    ).exists()


@pytest.mark.django_db
def test_unauthorized_user_gets_403(client, user, curriculum):
    """Unauthorized users are forbidden."""
    client.force_login(user)
    url = reverse("create_student")
    response = client.get(url)
    assert response.status_code == 403
