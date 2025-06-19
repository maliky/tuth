"""Module to test some function of the people app."""

import pytest
from django.contrib.auth.models import User

from app.people.utils import mk_username, split_name


def test_mk_username_default():
    """Default username generation without uniqueness."""
    assert mk_username("Isaac", "Yancy") == "iyancy"


@pytest.mark.django_db
def test_mk_username_unique_appends_numbers():
    """Unique usernames append incremental numbers when needed."""
    User.objects.create_user(username="iyancy")
    User.objects.create_user(username="iyancy2")

    assert mk_username("Isaac", "Yancy", unique=True) == "iyancy3"


@pytest.mark.parametrize(
    "raw,prefix,first,middle,last,suffix",
    [
        ("Doc. Malik K. Kone,  Ph.D.", "Doc.", "Malik", "K", "Kone", "PhD"),
        ("Dr Kone  Ph.D.", "Dr.", "", "", "Kone", "PhD"),
        ("Rev Fr M Kone,  Ph.D.", "Doc.", "M", "", "Kone", "PhD"),
        ("Blayon, O. G", "", "O.", "G.", "Blayon", ""),
        ("Blayon O G.", "", "O.", "G.", "Blayon", ""),
        ("A. J K. Doe", "", "A.", "J. K.", "Doe", ""),
        ("Al J. K. Doe", "", "Al", "J. K.", "Doe", ""),
        ("Al Doe", "", "Al", "", "Doe", ""),
        ("Doe A.", "", "A.", "", "Doe", ""),
        ("B Doe", "", "B.", "", "Doe", ""),
        ("Doe", "", "", "", "Doe", ""),
        (" Doc Oum", "Doc.", "", "", "Oum", ""),
    ],
)
def test_split_name_initial_patterns(raw, prefix, first, middle, last, suffix):
    res = split_name(raw)
    ref = (prefix, first, middle, last, suffix)
    assert res == ref, f"{ref} != {res} !"
