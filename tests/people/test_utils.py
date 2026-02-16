"""Module to test some function of the people app."""

import pytest
from django.db import IntegrityError, transaction

from app.people.utils import (
    extract_id_num,
    mk_username,
    split_name,
)


@pytest.mark.parametrize(
    "first,last,username",
    [
        ("Esop", "Thot", "esop.thot"),
        ("esop", "Thot", "esop.thot"),
        ("a", "Thot", "a.thot"),
        ("", "Thot", "thot"),
    ],
)
def test_mk_username_dft(first, last, username):
    """Default username generation without uniqueness."""
    _uname = mk_username(first, last)
    assert _uname == username, f"{first} {last} -> {_uname} != {username}"


@pytest.mark.django_db(transaction=True)
def test_mk_username_uniqness(user_factory):
    """Check if the username stay uniq with an increased by number."""
    username1 = mk_username("Esop", "Thot", prefix_len=2)  # esthot
    user1 = user_factory(username=username1)

    # create another user but with that username
    un2 = mk_username("Esai", "Thot", prefix_len=2)  # esthot
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _ = user_factory(username=un2)
            # should through UNIQUE constraint failed: auth_user.username

    username3 = mk_username(
        "Esai", "Thot", unique=True, prefix_len=2
    )  # esthot2, not esthot1
    user3 = user_factory(username=username3)

    assert username1 == "es.thot", f"un1={username1}"
    assert un2 == "es.thot", f"un2={un2}"
    assert username3 == "es.thot2", f"un3={username3}"
    assert user1.username == "es.thot", f"u1.username={user1.username}"
    assert user3.username == "es.thot2", f"u3.username={user3.username}"


# Doit tester la création d'un staff d'un student d'un donor vérifier les ID


@pytest.mark.parametrize(
    "raw,prefix,first,middle,last,suffix",
    [
        ("Doc. Malik K. Kone,  Ph.D.", "Doc.", "Malik", "K.", "KONE", "PhD"),
        ("Dr Kone  Ph.D.", "Dr.", "", "", "KONE", "PhD"),
        # ("Rev Fr M Kone,  Ph.D.", "Rev. Fr.", "M.", "", "Kone", "PhD"),
        ("Blayon, O. G", "", "O.", "G.", "BLAYON", ""),
        ("Blayon O G.", "", "O.", "G.", "BLAYON", ""),
        ("A. J K. Doe", "", "A.", "J. K.", "DOE", ""),
        ("Al J. K. Doe", "", "Al", "J. K.", "DOE", ""),
        ("Al Doe", "", "Al", "", "DOE", ""),
        ("Doe A.", "", "A.", "", "DOE", ""),
        ("B Doe", "", "B.", "", "DOE", ""),
        ("Doe", "", "", "", "DOE", ""),
        (" Doc Oum", "Doc.", "", "", "OUM", ""),
        # need to be consitent with number of name to distinguish the 2 below
        ("Nimely II, William N.", "", "William", "N.", "NIMELY-II", ""),
        ("Nimely, William G.", "", "William", "G.", "NIMELY", ""),
        ("Nimely Phd, William G.", "", "William", "G.", "NIMELY", "Phd"),
    ],
)
def test_split_name_initial_patterns(raw, prefix, first, middle, last, suffix):
    parts = split_name(raw).fullparts()
    ref = (prefix, first, middle, last, suffix)
    assert parts == ref, f"{parts} != {ref} !"


@pytest.mark.parametrize(
    "user_id,output",
    [("TU-123", 123), ("TU-00123", 123), ("00123", 123), ("123", 123)],
)
def test_extract_id_num(user_id, output):
    res = extract_id_num(user_id)
    assert res == output, f"{res} != {output}"
