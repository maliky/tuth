"""Test course admin module."""

import pytest
from django.contrib.admin.widgets import AutocompleteSelect

from django.urls import reverse
from app.academics.models import College, Course
from app.academics.admin.forms import CourseForm


@pytest.mark.django_db
def test_course_form_prefills_single_college():
    col = College.objects.create(code="ENG", fullname="Engineering")
    Course.objects.create(name="MAT", number="101", title="Math", college=col)
    form = CourseForm(data={"name": "MAT", "number": "101", "title": "New"})
    assert form.is_valid()
    assert form.cleaned_data["college"] == col


@pytest.mark.django_db
def test_course_form_autocomplete_multiple_colleges():
    c1 = College.objects.create(code="ENG", fullname="Engineering")
    c2 = College.objects.create(code="SCI", fullname="Science")
    Course.objects.create(name="CSC", number="101", title="Intro", college=c1)
    Course.objects.create(name="CSC", number="101", title="Other", college=c2)
    form = CourseForm(data={"name": "CSC", "number": "101", "title": "New"})
    widget = form.fields["college"].widget
    assert isinstance(widget, AutocompleteSelect)


@pytest.mark.django_db
def test_update_course_college_action(client, superuser):
    old = College.objects.create(code="ENG", fullname="Engineering")
    new = College.objects.create(code="SCI", fullname="Science")
    c1 = Course.objects.create(name="PHY", number="101", title="Physics", college=old)
    c2 = Course.objects.create(name="CHE", number="101", title="Chemistry", college=old)

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
