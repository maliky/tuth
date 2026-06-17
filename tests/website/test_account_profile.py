"""Account profile self-service regressions."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from app.people.models.staffs import Staff

pytestmark = pytest.mark.django_db


def _staff_user(username: str = "staff_profile_user") -> User:
    """Create a staff user with a linked staff profile."""
    user = User.objects.create_user(
        username,
        password="PassW0rd!",
        first_name="Staff",
        last_name="Member",
        email="staff.member@example.test",
    )
    Staff(user=user, phone_number="+231770000000").save()
    return user


def test_staff_dashboard_identity_links_to_self_profile(client) -> None:
    """Staff dashboards should use the person identity as the profile entry point."""
    user = _staff_user()
    client.force_login(user)

    response = client.get(reverse("staff_role_dashboard", args=["staff"]))

    assert response.status_code == 302
    assert response.url == reverse("account_profile")


def test_staff_dashboard_links_to_self_profile(client) -> None:
    """Staff dashboards should expose the shared profile page, not a profile clone."""
    user = _staff_user("staff_profile_link")
    client.force_login(user)

    response = client.get(reverse("staff_dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("account_profile") in content
    assert "Staff Member" in content
    assert "My Staff Workspace" not in content


def test_account_profile_defaults_to_read_only_presentation(client) -> None:
    """The profile page should present current data before asking users to edit."""
    user = _staff_user("staff_profile_read")
    client.force_login(user)

    response = client.get(reverse("account_profile"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Edit profile" in content
    assert "account-profile-overview-grid" in content
    assert "account-profile-card__hero" in content
    assert "account-profile-section--contact" in content
    assert "Save profile" not in content
    assert "Staff Member" in content
    assert "Contact" in content


def test_account_profile_edit_mode_shows_single_page_form(client) -> None:
    """Edit mode should reveal the form without leaving the profile page."""
    user = _staff_user("staff_profile_edit")
    client.force_login(user)

    response = client.get(f"{reverse('account_profile')}?mode=edit")
    content = response.content.decode()

    assert response.status_code == 200
    assert "Update personal profile" in content
    assert "Save profile" in content
    assert "Cancel" in content


def test_account_profile_updates_current_staff_contact_details(client) -> None:
    """The self-service profile form should mutate only the current user profile."""
    user = _staff_user("staff_profile_update")
    staff = user.staff
    client.force_login(user)

    response = client.post(
        reverse("account_profile"),
        {
            "prefix_name": "Dr.",
            "first_name": "Updated",
            "middle_name": "Middle",
            "last_name": "Person",
            "suffix_name": "Sr.",
            "email": "updated.person@example.test",
            "phone_number": "+231770000111",
            "physical_address": "Tubman Town, Harper",
            "birth_date": "1980-01-02",
            "birth_place": "Harper",
            "gender": "m",
            "nationality": "Liberian",
            "origin_county": "Maryland",
            "marital_status": "Single",
        },
        follow=True,
    )

    user.refresh_from_db()
    staff.refresh_from_db()
    assert response.status_code == 200
    assert user.first_name == "Updated"
    assert user.last_name == "Person"
    assert user.email == "updated.person@example.test"
    assert staff.long_name == "Dr. Updated Middle Person Sr."
    assert str(staff.phone_number) == "+231770000111"
    assert staff.physical_address == "Tubman Town, Harper"
    assert "Profile updated." in response.content.decode()
    assert "Edit profile" in response.content.decode()
