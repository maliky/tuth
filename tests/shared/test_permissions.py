"""Permission retrieval tests using django-guardian."""
from guardian.shortcuts import get_objects_for_user
import pytest

from app.academics.models.college import College

pytestmark = pytest.mark.django_db


def _check_only_default_visible(user, college):
    objs = get_objects_for_user(
        user,
        "academics.view_college",
        College,
        use_groups=False,
        accept_global_perms=False,
    )
    assert list(objs) == [college]


def _check_all_visible(user, college, college_other):
    objs = get_objects_for_user(user, "academics.view_college", College)
    assert set(objs) == {college, college_other}


# TO REVIEW
# def test_object_level_access_restricted(
#     dean_user, chair_user, faculty_user, student_user, college, college_other
# ):
#     """Users see only permitted object when using object-level perms."""

#     for user in (dean_user, chair_user, faculty_user, student_user):
#         _check_only_default_visible(user, college)


# def test_model_level_access(
#     dean_user, chair_user, faculty_user, student_user, college, college_other
# ):
#     """Model-level permissions via groups return all objects."""

#     for user in (dean_user, chair_user, faculty_user, student_user):
#         _check_all_visible(user, college, college_other)
