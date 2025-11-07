"""Smoke tests for the public landing page."""

from __future__ import annotations

import pytest
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


def test_landing_page_renders_with_hero(live_server, selenium_driver) -> None:
    """Ensure the marketing hero renders for prospective students."""
    url = f"{live_server.url}{reverse('landing')}"
    selenium_driver.get(url)

    hero_heading = selenium_driver.find_element(By.CSS_SELECTOR, ".carousel-caption h2")
    assert "Build Your Career" in hero_heading.text

    mockup_banner = selenium_driver.find_element(By.CSS_SELECTOR, "main h3")
    assert "mock-up landing page" in mockup_banner.text


def test_tusis_button_routes_to_admin_login(live_server, selenium_driver) -> None:
    """Validate that the Tusis CTA links to Django’s admin login."""
    url = f"{live_server.url}{reverse('landing')}"
    selenium_driver.get(url)

    tusis_button = WebDriverWait(selenium_driver, 10).until(
        EC.element_to_be_clickable((By.ID, "tusis-btn"))
    )
    tusis_button.click()

    WebDriverWait(selenium_driver, 10).until(EC.title_contains("Log in"))
    assert "Log in" in selenium_driver.title
    assert "Django administration" in selenium_driver.page_source

