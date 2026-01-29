"""BDD coverage for portal role dashboards."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, parsers, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urlparse

from tests.bdd.fixtures import PortalContext
from tests.selenium.fixtures_portal import _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


@scenario(
    "features/portal_roles.feature", "User lands on the correct dashboard"
)
def test_portal_role_dashboards_bdd():
    """Drive dashboard landing scenarios for portal roles."""


@scenario(
    "features/portal_roles.feature", "Role dashboards show expected actions"
)
def test_portal_role_actions_bdd():
    """Drive role action visibility scenarios."""


@scenario(
    "features/portal_roles.feature",
    "Registrar without officer permissions cannot manage semester windows",
)
def test_portal_registrar_action_restriction_bdd():
    """Drive the registrar restriction scenario."""


def _parse_bool(value: str) -> bool:
    """Interpret feature file booleans."""
    return value.strip().lower() in {"yes", "true", "1"}


def _parse_roles(raw_role: str) -> list[str]:
    """Normalize a role string into a list of groups."""
    role = raw_role.strip()
    return [role] if role else []


def _action_paths(driver) -> set[str]:
    """Return the set of action button href paths on the dashboard."""
    links = driver.find_elements(By.CSS_SELECTOR, ".action-card a.btn")
    paths: set[str] = set()
    for link in links:
        href = link.get_attribute("href")
        if href:
            paths.add(urlparse(href).path)
    return paths


@given(
    parsers.re(
        r'a portal user "(?P<username>.+)" with role "(?P<role>.*)" and student "(?P<student>.+)"'
    )
)
def portal_user_with_role(
    portal_context: PortalContext,
    portal_user_factory,
    username: str,
    role: str,
    student: str,
) -> None:
    """Provision a portal user with optional staff role and student profile."""
    is_student = _parse_bool(student)
    portal_context.username = username
    portal_context.is_student = is_student
    portal_user_factory(
        username,
        groups=_parse_roles(role),
        student=is_student,
    )


@when("the user logs in to the portal")
def user_logs_in_to_portal(
    portal_context: PortalContext, live_server, selenium_driver
) -> None:
    """Log in as the prepared portal user."""
    logout_url = f"{live_server.url}{reverse('portal_logout')}"
    selenium_driver.get(logout_url)
    assert portal_context.username is not None
    _login_to_portal(selenium_driver, live_server, portal_context.username)


@then(parsers.parse('the dashboard heading includes "{heading}"'))
def dashboard_heading_includes(
    portal_context: PortalContext, selenium_driver, heading: str
) -> None:
    """Confirm the expected dashboard heading is visible."""
    staff_heading = (By.CSS_SELECTOR, ".staff-shell__title")
    student_heading = (By.CSS_SELECTOR, ".portal-header h1")
    if portal_context.is_student:
        heading_locator = student_heading
    else:
        heading_locator = staff_heading
    WebDriverWait(selenium_driver, 20).until(
        EC.text_to_be_present_in_element(heading_locator, heading)
    )
    assert heading in selenium_driver.find_element(*heading_locator).text


@then(parsers.parse('the dashboard actions include "{actions}"'))
def dashboard_actions_include(selenium_driver, actions: str) -> None:
    """Ensure the dashboard actions include the expected links."""
    expected_paths = {reverse(name.strip()) for name in actions.split(",") if name.strip()}

    def _actions_loaded(driver):
        return expected_paths.issubset(_action_paths(driver))

    WebDriverWait(selenium_driver, 10).until(_actions_loaded)


@then(parsers.parse('the dashboard actions do not include "{action}"'))
def dashboard_actions_exclude(selenium_driver, action: str) -> None:
    """Ensure the dashboard actions do not include the forbidden link."""
    action_paths = _action_paths(selenium_driver)
    assert reverse(action) not in action_paths
