"""Test college widget module."""

from types import SimpleNamespace

import pytest

from app.academics.admin.widgets import CollegeWidget
from app.academics.models.college import College


@pytest.mark.django_db
def test_college_widget_tracks_new_colleges() -> None:
    widget: CollegeWidget = CollegeWidget(College, "code")
    dummy = SimpleNamespace(_new_colleges=set())
    widget._resource = dummy

    college: College = widget.clean("COET")
    assert college.code == "COET"
    assert "COET" in dummy._new_colleges


@pytest.mark.django_db
def test_college_widget_skips_existing_colleges():
    College.objects.create(code="COAS", fullname="Arts")
    cw = CollegeWidget(College, "code")
    dummy = SimpleNamespace(_new_colleges=set())
    cw._resource = dummy

    obj = cw.clean("COAS")

    assert obj.code == "COAS"
    assert not dummy._new_colleges
