"""Browser smoke tests for registrar transcript downloads."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.registry.models.grade import Grade, GradeValue
from tests.selenium.fixtures_portal import _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


def _grade_value(code: str) -> GradeValue:
    """Return a grade value for transcript fixtures."""
    grade_value, _created = GradeValue.objects.get_or_create(code=code)
    return grade_value


def _wait_for_org_download(download_dir: Path) -> Path:
    """Return the completed Org download path from a browser download directory."""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        candidates = [
            path
            for path in download_dir.glob("*.org")
            if not path.name.endswith(".crdownload") and path.stat().st_size > 0
        ]
        if candidates:
            return candidates[0]
        time.sleep(0.2)
    raise AssertionError("Timed out waiting for transcript Org download.")


def test_registrar_downloads_transcript_org_source_in_browser(
    selenium_driver,
    live_server,
    tmp_path: Path,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Clicking Download Org source should save an Org transcript file."""
    user = reg_user_factory("registrar_selenium_org")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="409",
        curriculum_short_name="CURRI_TRANSCRIPT_SELENIUM",
    )
    student = reg_std_factory("registrar_selenium_org_student", curriculum, current)
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))
    selenium_driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(tmp_path)},
    )

    _login_to_portal(selenium_driver, live_server, user.username)
    transcript_url = (
        f"{live_server.url}{reverse('reg_grade_transcript', args=[student.id])}"
    )
    selenium_driver.get(transcript_url)
    download_link = WebDriverWait(selenium_driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-transcript-org-download]"))
    )
    download_link.click()
    org_path = _wait_for_org_download(tmp_path)
    org_source = org_path.read_text()

    assert org_path.name.endswith(".org")
    assert "#+LATEX_CLASS: tutranscript" in org_source
    assert "\\TUPrintTranscript" in org_source
