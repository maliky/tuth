"""BDD coverage for the public landing page."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


@scenario("features/landing_page.feature", "Visitor sees the landing page hero")
def test_landing_page_hero_bdd():
    """Drive the landing page hero scenario."""


@scenario("features/landing_page.feature", "Visitor uses the Tusis button")
def test_landing_page_tusis_button_bdd():
    """Drive the portal CTA scenario."""


@given("the visitor is on the landing page")
def visitor_on_landing_page(live_server, selenium_driver) -> None:
    """Open the public landing page."""
    url = f"{live_server.url}{reverse('landing')}"
    selenium_driver.get(url)


@then("the landing page hero is visible")
def landing_page_hero_visible(selenium_driver) -> None:
    """Ensure the marketing hero is present."""
    hero_heading = WebDriverWait(selenium_driver, 10).until(
        EC.visibility_of_element_located((By.ID, "landing-hero-title"))
    )
    assert "One secure entry point" in hero_heading.text


@then("the service status card is visible")
def landing_page_service_status_visible(selenium_driver) -> None:
    """Ensure the landing service status card is visible."""
    status_card = WebDriverWait(selenium_driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".landing-service-card h2"))
    )
    assert "Ready for campus workflow testing" in status_card.text


@when("the visitor clicks the Tusis button")
def visitor_clicks_tusis_button(selenium_driver) -> None:
    """Trigger the portal CTA from the landing page."""
    tusis_button = WebDriverWait(selenium_driver, 10).until(
        EC.element_to_be_clickable((By.ID, "tusis-btn"))
    )
    tusis_button.click()


@then("the portal login form is shown")
def portal_login_form_shown(selenium_driver) -> None:
    """Wait for the portal login form fields."""
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    assert "Sign in" in selenium_driver.page_source
