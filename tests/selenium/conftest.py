"""Shared Selenium fixtures (Chromium/Chrome)."""

pytest_plugins = [
    "tests.selenium.fixtures_browser",
    "tests.selenium.fixtures_portal",
    "tests.selenium.fixtures_registrar_grades",
    "tests.selenium.fixtures_registrar",
    "tests.selenium.fixtures_finance",
]
