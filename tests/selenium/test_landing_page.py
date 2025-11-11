"""Smoke tests for the public landing page."""
from __future__ import annotations

import socket

import pytest
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def _can_bind_localhost() -> bool:
    """Best-effort probe to verify the codex sandbox allows opening sockets."""
    sock: socket.socket | None = None
    try:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
    except OSError:
        return False
    finally:
        if sock:
            sock.close()
    return True


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


def test_landing_page_renders_with_hero(live_server, selenium_driver) -> None:
    """Ensure the marketing hero renders for prospective students."""
    url = f"{live_server.url}{reverse('landing')}"
    selenium_driver.get(url)

    hero_heading = selenium_driver.find_element(By.CSS_SELECTOR, ".carousel-caption h2")
    assert "Build Your Career" in hero_heading.text

    mockup_banner = selenium_driver.find_element(By.CSS_SELECTOR, "main h3")
    assert "mock-up landing page" in mockup_banner.text


def test_tusis_button_routes_to_portal_login(live_server, selenium_driver) -> None:
    """Validate that the Tusis CTA links to the unified portal login."""
    url = f"{live_server.url}{reverse('landing')}"
    selenium_driver.get(url)

    tusis_button = WebDriverWait(selenium_driver, 10).until(
        EC.element_to_be_clickable((By.ID, "tusis-btn"))
    )
    tusis_button.click()

    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    assert "Sign in" in selenium_driver.page_source
