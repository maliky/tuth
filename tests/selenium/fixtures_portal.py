"""Shared portal fixtures for Selenium tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from selenium.webdriver.common.by import By

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.timetable.models.semester import Semester

TEST_PASSWORD = "PassW0rd!"


@pytest.fixture
def portal_user_factory(semester: Semester):
    """Create portal users with optional student profile and group assignments."""
    UserModel = get_user_model()

    def _build(
        username: str,
        *,
        groups: list[str] | None = None,
        student: bool = False,
        semester_override: Semester | None = None,
    ):
        first_name = "Test"
        last_name = username.replace("_", " ").title()

        user, created = UserModel.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if created:
            user.set_password(TEST_PASSWORD)
        else:
            user.groups.clear()
            user.set_password(TEST_PASSWORD)
            user.first_name = first_name
            user.last_name = last_name
        user.save()

        for group_name in groups or []:
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
        if student:
            active_semester = semester_override or semester
            student_obj, _ = Student.objects.update_or_create(
                user=user,
                defaults={
                    "entry_semester": active_semester,
                    "last_enrolled_semester": active_semester,
                },
                username=user.username,
            )
            set_primary_std_curri_enroll(
                student_obj,
                Curriculum.get_dft(),
                entry_semester_id=active_semester.id,
            )
        return user

    return _build


def _login_to_portal(driver, live_server, username):
    """Authenticate the user via the portal login form."""
    login_url = f"{live_server.url}{reverse('portal_login')}"
    driver.get(login_url)
    driver.find_element(By.ID, "id_username").send_keys(username)
    driver.find_element(By.ID, "id_password").send_keys(TEST_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
