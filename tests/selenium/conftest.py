"""Shared Selenium fixtures."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

_DEFAULT_IMPLICIT_WAIT = 5


def _bool_flag(value: str | None, default: bool = True) -> bool:
    """Interpret environment variables as booleans."""
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _implicit_wait_seconds(raw_value: str | None) -> int:
    """Return a safe implicit wait timeout."""
    if not raw_value:
        return _DEFAULT_IMPLICIT_WAIT
    try:
        seconds = int(raw_value)
    except ValueError:
        return _DEFAULT_IMPLICIT_WAIT
    return seconds if seconds > 0 else _DEFAULT_IMPLICIT_WAIT


def _build_chrome(headless: bool, remote_url: str | None) -> WebDriver:
    options = ChromeOptions()
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1400,900")
    if headless:
        options.add_argument("--headless=new")

    if remote_url:
        return webdriver.Remote(command_executor=remote_url, options=options)

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _build_firefox(headless: bool, remote_url: str | None) -> WebDriver:
    options = FirefoxOptions()
    options.add_argument("--width=1400")
    options.add_argument("--height=900")
    if headless:
        options.add_argument("--headless")

    if remote_url:
        return webdriver.Remote(command_executor=remote_url, options=options)

    service = FirefoxService(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=options)


def _create_driver() -> WebDriver:
    browser = os.getenv("SELENIUM_BROWSER", "chrome").strip().lower()
    remote_url = os.getenv("SELENIUM_REMOTE_URL")
    headless = _bool_flag(os.getenv("SELENIUM_HEADLESS"), default=True)

    if browser in {"chrome", "chromium"}:
        return _build_chrome(headless=headless, remote_url=remote_url)
    if browser in {"firefox", "ff"}:
        return _build_firefox(headless=headless, remote_url=remote_url)

    raise RuntimeError(
        f"Unsupported browser '{browser}'. "
        "Set SELENIUM_BROWSER to 'chrome' or 'firefox'."
    )


@pytest.fixture(scope="session")
def selenium_driver() -> Generator[WebDriver, None, None]:
    """Provide a configured Selenium WebDriver."""
    driver = _create_driver()
    driver.implicitly_wait(_implicit_wait_seconds(os.getenv("SELENIUM_IMPLICIT_WAIT")))
    try:
        yield driver
    finally:
        driver.quit()

