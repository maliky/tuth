"""Test course admin module."""

import pytest
from django.contrib.admin.widgets import AutocompleteSelect

from django.urls import reverse

from app.academics.admin.forms import CourseForm


@pytest.mark.django_db
def test_course_form_prefills_single_college(college_factory, course_factory):
    col = college_factory(code="ENG", fullname="Engineering")
    course_factory(name="MAT", number="101", title="Math", college=col)
    form = CourseForm(data={"name": "MAT", "number": "101", "title": "New"})
    assert form.is_valid()
    assert form.cleaned_data["college"] == col


@pytest.mark.django_db
def test_course_form_autocomplete_multiple_colleges(college_factory, course_factory):
    c1 = college_factory(code="ENG", fullname="Engineering")
    c2 = college_factory(code="SCI", fullname="Science")
    course_factory(name="CSC", number="101", title="Intro", college=c1)
    course_factory(name="CSC", number="101", title="Other", college=c2)
    form = CourseForm(data={"name": "CSC", "number": "101", "title": "New"})
    widget = form.fields["college"].widget
    assert isinstance(widget, AutocompleteSelect)


@pytest.mark.django_db
def test_update_course_college_action(client, superuser, college_factory, course_factory):
    old = college_factory(code="ENG", fullname="Engineering")
    new = college_factory(code="SCI", fullname="Science")
    c1 = course_factory(name="PHY", number="101", title="Physics", college=old)
    c2 = course_factory(name="CHE", number="101", title="Chemistry", college=old)

    client.force_login(superuser)
    url = reverse("admin:academics_course_changelist")
    data = {
        "action": "update_college",
        "_selected_action": [c1.pk, c2.pk],
        "apply": "yes",
        "college": new.pk,
    }
    client.post(url, data)

    c1.refresh_from_db()
    c2.refresh_from_db()
    assert c1.college == new
    assert c2.college == new
