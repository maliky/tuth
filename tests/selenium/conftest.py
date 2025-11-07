"""Shared Selenium fixtures (Brave-only)."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as BraveOptions
from selenium.webdriver.chrome.service import Service as BraveService
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

_DEFAULT_IMPLICIT_WAIT = 5


def _bool_flag(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _implicit_wait_seconds(raw_value: str | None) -> int:
    if not raw_value:
        return _DEFAULT_IMPLICIT_WAIT
    try:
        seconds = int(raw_value)
    except ValueError:
        return _DEFAULT_IMPLICIT_WAIT
    return seconds if seconds > 0 else _DEFAULT_IMPLICIT_WAIT


def _build_brave(headless: bool, remote_url: str | None) -> WebDriver:
    """Create a Brave WebDriver instance."""
    options = BraveOptions()
    options.binary_location = "/usr/bin/brave-browser" 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1400,900")
    if headless:
        options.add_argument("--headless=new")

    if remote_url:
        return webdriver.Remote(command_executor=remote_url, options=options)

    service = BraveService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _create_driver() -> WebDriver:
    """Return a configured Brave WebDriver."""
    remote_url = os.getenv("SELENIUM_REMOTE_URL")
    headless = _bool_flag(os.getenv("SELENIUM_HEADLESS"), default=True)
    return _build_brave(headless=headless, remote_url=remote_url)


@pytest.fixture(scope="session")
def selenium_driver() -> Generator[WebDriver, None, None]:
    """Provide a configured Brave WebDriver."""
    driver = _create_driver()
    driver.implicitly_wait(_implicit_wait_seconds(os.getenv("SELENIUM_IMPLICIT_WAIT")))
    try:
        yield driver
    finally:
        driver.quit()
