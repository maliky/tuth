import pytest
from django.contrib.admin.widgets import AutocompleteSelect

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
