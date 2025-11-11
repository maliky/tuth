"""Role-based portal smoke tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urlparse

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.timetable.models.semester import Semester
from tests.selenium.test_landing_page import _can_bind_localhost

TEST_PASSWORD = "Passw0rd!"

ROLE_CASES = [
    ("instructor_user", {"groups": ["Instructor"]}, "Instruction Hub"),
    ("student_user", {"student": True, "groups": []}, "Student Dashboard"),
    ("chair_user", {"groups": ["Chair"]}, "Chair Curriculum Center"),
    ("dean_user", {"groups": ["Dean"]}, "Dean Oversight"),
    ("vpaa_user", {"groups": ["VPAA"]}, "VPAA Approval Hub"),
    ("registrar_user", {"groups": ["Registrar"]}, "Registrar Lifecycle Ops"),
    (
        "scholarship_user",
        {"groups": ["Scholarship Officer"]},
        "Scholarship Office",
    ),
    ("finance_user", {"groups": ["Finance"]}, "Finance & Holds"),
    ("finance_officer_user", {"groups": ["Finance Officer"]}, "Finance Officer Control"),
]

ACTION_CASES = [
    ("registrar_officer_user", {"groups": ["Registrar Officer"]}, ["registrar_course_windows"]),
    ("enrollment_user", {"groups": ["Enrollment"]}, ["student_list", "create_student"]),
    ("enrollment_officer_user", {"groups": ["Enrollment Officer"]}, ["student_list", "create_student"]),
]


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]

if not _can_bind_localhost():
    pytestmark.append(
        pytest.mark.skip(
            reason="Selenium tests require permission to bind localhost sockets."
        )
    )


@pytest.fixture
def portal_user_factory(semester):
    """Create portal users with optional student profile and group assignments."""
    UserModel = get_user_model()

    def _build(username: str, *, groups: list[str] | None = None, student: bool = False):
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
            Student.objects.update_or_create(
                user=user,
                defaults={
                    "curriculum": Curriculum.get_default(),
                    "entry_semester": semester,
                    "current_enrolled_semester": semester,
                },
                username=user.username,
            )
        return user

    return _build


def _login_to_portal(driver, live_server, username):
    login_url = f"{live_server.url}{reverse('portal_login')}"
    driver.get(login_url)
    driver.find_element(By.ID, "id_username").send_keys(username)
    driver.find_element(By.ID, "id_password").send_keys(TEST_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()


def _action_paths(driver) -> set[str]:
    """Return the set of action button href paths on the dashboard."""
    links = driver.find_elements(By.CSS_SELECTOR, "section.container .card a.btn")
    paths: set[str] = set()
    for link in links:
        href = link.get_attribute("href")
        if href:
            paths.add(urlparse(href).path)
    return paths


@pytest.mark.parametrize("username,config,expected_heading", ROLE_CASES)
def test_role_dashboards(
    live_server,
    selenium_driver,
    portal_user_factory,
    username,
    config,
    expected_heading,
):
    """Each person lands on the appropriate dashboard after login."""
    portal_user_factory(username, **config)
    _login_to_portal(selenium_driver, live_server, username)

    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), expected_heading)
    )

    logout_url = f"{live_server.url}{reverse('portal_logout')}"
    selenium_driver.get(logout_url)

    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )


@pytest.mark.parametrize("username,config,action_names", ACTION_CASES)
def test_role_dashboards_show_expected_actions(
    live_server,
    selenium_driver,
    portal_user_factory,
    username,
    config,
    action_names,
):
    """Specific staff roles expose their tool links as dashboard actions."""
    portal_user_factory(username, **config)
    _login_to_portal(selenium_driver, live_server, username)

    expected_paths = {reverse(name) for name in action_names}

    def _actions_loaded(driver):
        return expected_paths.issubset(_action_paths(driver))

    WebDriverWait(selenium_driver, 10).until(_actions_loaded)

    selenium_driver.get(f"{live_server.url}{reverse('portal_logout')}")
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )


def test_registrar_cannot_manage_semester_windows(
    live_server,
    selenium_driver,
    portal_user_factory,
):
    """Non-officer registrars should not see the semester window action."""
    username = "registrar_basic"
    portal_user_factory(username, groups=["Registrar"])
    _login_to_portal(selenium_driver, live_server, username)

    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element(
            (By.TAG_NAME, "h1"), "Registrar Lifecycle Ops"
        )
    )

    action_paths = _action_paths(selenium_driver)
    assert reverse("registrar_course_windows") not in action_paths
