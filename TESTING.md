## Testing Guide

This document describes how to run the test suites and how fixtures are organized.

### Quick Start

Run the full suite:

```bash
pytest
```

Run a single app suite:

```bash
pytest tests/registry
```

Run one test file:

```bash
pytest tests/registry/test_grade.py
```

### Test Layout

- App-focused tests live under `tests/<app>/test_*.py`.
- Cross-cutting and shared tests live under `tests/shared`.
- Selenium/browser tests live under `tests/selenium`.
- Feature-style tests live under `tests/features`.

### Fixtures and Factories

- Global fixture registration is centralized in `tests/conftest.py`.
- Per-app fixture factories live in:
  - `tests/academics/fixture.py`
  - `tests/people/fixture.py`
  - `tests/registry/fixture.py`
  - `tests/timetable/fixture.py`
  - `tests/spaces/fixture.py`
  - `tests/finance/fixture.py`
  - `tests/shared/fixture.py`
- Permission fixtures live in `tests/shared/permissions_fixtures.py`.

The test fixtures use factory-style helpers (for example, `student_factory` and
`section_factory`) to keep test setup consistent and concise.

### Django DB Usage

Most model-focused test files use the `pytest.mark.django_db` mark at module
scope to enable database access. If you add new model tests, follow the same
pattern.

### Selenium Tests

Selenium tests are marked with `pytest.mark.selenium` and rely on Django’s
`live_server` fixture. The Selenium fixtures are defined in
`tests/selenium/conftest.py`.

Important:
- Use the system `chromedriver` at `/usr/bin/chromedriver` (version 142.x).
- Do not downgrade to webdriver-manager defaults (114.x), which breaks local
  browsers.

Run Selenium tests explicitly:

```bash
pytest -m selenium
```

### Feature Tests

Feature-style tests use pytest-bdd and live in `tests/features`.

### Notes and TODOs

- `tests/finance/fixture.py` contains commented-out fixtures pending finance
  model updates.
- `tests/finance/test_donor_scholarship.py` includes TODOs for reverse relation
  coverage.
