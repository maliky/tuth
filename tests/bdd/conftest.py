"""Shared pytest-bdd fixtures."""

pytest_plugins = [
    "tests.bdd.fixtures",
    "tests.selenium.fixtures_portal",
    "tests.selenium.fixtures_registrar_grades",
    "tests.selenium.fixtures_finance",
]
