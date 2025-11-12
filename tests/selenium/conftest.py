"""Shared Selenium fixtures (Chromium/Chrome)."""

from __future__ import annotations

import os
import shutil
from typing import Generator

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

_DEFAULT_IMPLICIT_WAIT = 5
_PREFERRED_DRIVER_VERSION = "142.0.7444.61"


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


def _resolve_chrome_binary() -> str | None:
    """Return the first available browser binary."""
    candidates = [
        os.getenv("CHROME_BINARY"),
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _resolve_chromedriver_path() -> str | None:
    """Return the chromedriver binary path if already installed on the system."""
    candidates = [
        os.getenv("CHROMEDRIVER_PATH"),
        shutil.which("chromedriver"),
        "/usr/bin/chromedriver",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _build_chromium(headless: bool, remote_url: str | None) -> WebDriver:
    """Create a Chromium/WebDriver instance."""
    options = ChromeOptions()
    binary_path = _resolve_chrome_binary()
    if binary_path:
        options.binary_location = binary_path
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1400,900")
    if headless:
        options.add_argument("--headless=new")

    if remote_url:
        return webdriver.Remote(command_executor=remote_url, options=options)

    driver_path = _resolve_chromedriver_path()
    if driver_path:
        service = ChromeService(executable_path=driver_path)
    else:
        version = os.getenv("CHROMEDRIVER_VERSION") or _PREFERRED_DRIVER_VERSION
        os.environ["WDM_CHROMEDRIVER_VERSION"] = version
        manager = ChromeDriverManager(driver_version=version)
        service = ChromeService(manager.install())
    return webdriver.Chrome(service=service, options=options)


def _create_driver() -> WebDriver:
    """Return a configured Brave WebDriver."""
    remote_url = os.getenv("SELENIUM_REMOTE_URL")
    headless = _bool_flag(os.getenv("SELENIUM_HEADLESS"), default=True)
    return _build_chromium(headless=headless, remote_url=remote_url)


@pytest.fixture(scope="session")
def selenium_driver() -> Generator[WebDriver, None, None]:
    """Provide a configured Brave WebDriver."""
    driver = _create_driver()
    driver.implicitly_wait(_implicit_wait_seconds(os.getenv("SELENIUM_IMPLICIT_WAIT")))
    try:
        yield driver
    finally:
        driver.quit()
