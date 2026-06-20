"""Browser smoke tests for registrar transcript downloads."""

from __future__ import annotations

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


def test_registrar_transcript_page_hides_org_source_download_in_browser(
    selenium_driver,
    live_server,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar transcript preview should expose PDF layout controls only."""
    user = reg_user_factory("registrar_selenium_org_hidden")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="409",
        curriculum_short_name="CURRI_TRANSCRIPT_SELENIUM",
    )
    student = reg_std_factory(
        "registrar_selenium_org_hidden_student", curriculum, current
    )
    Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    _login_to_portal(selenium_driver, live_server, user.username)
    transcript_url = (
        f"{live_server.url}{reverse('reg_grade_transcript', args=[student.id])}"
    )
    selenium_driver.get(transcript_url)
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[data-transcript-layout-select]")
        )
    )

    assert "Download PDF" in selenium_driver.page_source
    assert "Download Org source" not in selenium_driver.page_source
    assert not selenium_driver.find_elements(
        By.CSS_SELECTOR, "[data-transcript-org-download]"
    )
