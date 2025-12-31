"""Test if student has email."""
import pytest
from django.contrib.auth.models import User

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student


@pytest.mark.django_db
def test_student_email_uses_username_prefix():
    """Student email prefix matches username; no extra suffixes inserted."""
    user = User.objects.create_user(username="janedoe", first_name="Jane", last_name="Doe")
    student = Student.objects.create(user=user, curriculum=Curriculum.get_default())
    
    email = student.mk_email()
    assert email.startswith("janedoe"), f"email should start with username, got {email}"
    assert email.endswith(Student.EMAIL_SUFFIX), "Email suffix should match student suffix"
