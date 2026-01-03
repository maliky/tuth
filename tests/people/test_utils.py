"""Module to test some function of the people app."""

import pytest
from django.db import IntegrityError, transaction

from app.people.utils import (
    extract_id_num,
    mk_username,
    split_name,
    # name_distance,
    # names_match,
    # name_similarity_matrix,
)


@pytest.mark.parametrize(
    "first,last,username",
    [
        ("Esop", "Thot", "esthot"),
        ("esop", "Thot", "esthot"),
        ("a", "Thot", "athot"),
        ("", "Thot", "thot"),
    ],
)
def test_mk_username_default(first, last, username):
    """Default username generation without uniqueness."""
    _uname = mk_username(first, last, prefix_len=2)
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

    assert username1 == "esthot", f"un1={username1}"
    assert un2 == "esthot", f"un2={un2}"
    assert username3 == "esthot2", f"un3={username3}"
    assert user1.username == "esthot", f"u1.username={user1.username}"
    assert user3.username == "esthot2", f"u3.username={user3.username}"


# Doit tester la création d'un staff d'un student d'un donor vérifier les ID


@pytest.mark.parametrize(
    "raw,prefix,first,middle,last,suffix",
    [
        ("Doc. Malik K. Kone,  Ph.D.", "Doc.", "Malik", "K.", "Kone", "PhD"),
        ("Dr Kone  Ph.D.", "Dr.", "", "", "Kone", "PhD"),
        # ("Rev Fr M Kone,  Ph.D.", "Rev. Fr.", "M.", "", "Kone", "PhD"),
        ("Blayon, O. G", "", "O.", "G.", "Blayon", ""),
        ("Blayon O G.", "", "O.", "G.", "Blayon", ""),
        ("A. J K. Doe", "", "A.", "J. K.", "Doe", ""),
        ("Al J. K. Doe", "", "Al", "J. K.", "Doe", ""),
        ("Al Doe", "", "Al", "", "Doe", ""),
        ("Doe A.", "", "A.", "", "Doe", ""),
        ("B Doe", "", "B.", "", "Doe", ""),
        ("Doe", "", "", "", "Doe", ""),
        (" Doc Oum", "Doc.", "", "", "Oum", ""),
        # need to be consitent with number of name to distinguish the 2 below
        ("Nimely, II, William N.", "", "William", "N.", "NimelyII", ""),
        ("Nimely, William G.", "", "William", "G.", "Nimely", ""),
    ],
)
def test_split_name_initial_patterns(raw, prefix, first, middle, last, suffix):
    parts = split_name(raw).parts()
    ref = (prefix, first, middle, last, suffix)
    assert parts == ref, f"{parts} != {ref} !"


@pytest.mark.parametrize(
    "user_id,output",
    [("TU-123", 123), ("TU-00123", 123), ("00123", 123), ("123", 123)],
)
def test_extract_id_num(user_id, output):
    res = extract_id_num(user_id)
    assert res == output, f"{res} != {output}"


# @pytest.mark.parametrize(
#     "left,right,expected",
#     [
#         ("Abraham W. Harmon", "Harmon, Abraham W", 0.1),
#         ("Virginia Blyee", "Blyee, Virginia", 0.1),
#         ("Sylvester Nah", "Nah Sylvester", 0.3),
#     ],
# )
# def test_name_distance_symmetry(left, right, expected):
#     """Distance should be near zero for reordered/normalized names."""
#     dist = name_distance(left, right)
#     assert dist < expected, f"{left, right}: {dist} != {expected}"


# @pytest.mark.parametrize(
#     "left,right,expected",
#     [
#         ("Abubarkar Yaradua", "Yaradua Abubarkar", 1),
#         ("Abubarkar Yaradua", "Yaradu Abubarkar", 1),
#         ("Abubarkar Yaradua", "Abuabrkar Yardaua", 1),
#         ("Abraham Gerard", "Virginia Blyee", 0.05),
#     ],
# )
# def test_names_match_threshold(left, right, expected):
#     """names_match should respect thresholds."""
#     if expected == 1:
#         assert names_match(left, right), f"{left, right}"
#     else:
#         assert not names_match(
#             left, right, threshold=expected
#         ), f"{left, right} - {names_match(left, right, threshold=expected)}"
