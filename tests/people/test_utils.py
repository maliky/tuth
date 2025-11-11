"""Module to test some function of the people app."""
import pytest
from django.db import IntegrityError, transaction

from app.people.utils import (
    extract_id_num,
    mk_username,
    split_name,
    ensure_unique_usernames,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # no duplicates → unchanged
        (["alice", "bob", "charlie"], ["alice", "bob", "charlie"]),
        # one duplicate → numbered starting at 2
        (["alice", "bob", "alice"], ["alice", "bob", "alice2"]),
        # two duplicates of same name
        (["x", "x", "x"], ["x", "x2", "x3"]),
        # mixed-case duplicates should still collide
        (["Foo", "foo", "Foo"], ["Foo", "foo2", "Foo3"]),
        # non-consecutive duplicates
        (["jan", "feb", "jan", "mar", "jan"], ["jan", "feb", "jan2", "mar", "jan3"]),
    ],
)
def test_ensure_unique_usernames(raw, expected):
    """Ensure ensure_unique_usernames appends numeric suffixes starting at 2."""
    result = ensure_unique_usernames(raw)
    assert result == expected, f"{raw!r} -> {result!r} (expected {expected!r})"


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
    assert _uname == username, f"{first} {last} {_uname}-> != {username}"


@pytest.mark.django_db(transaction=True)
def test_mk_username_uniqness(user_factory):
    """Check if the username stay uniq with an increased by number."""
    un1 = mk_username("Esop", "Thot", prefix_len=2)  # esthot
    u1 = user_factory(username=un1)

    # create another user but with that username
    un2 = mk_username("Esai", "Thot", prefix_len=2)  # esthot
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _ = user_factory(username=un2)
            # should through UNIQUE constraint failed: auth_user.username

    un3 = mk_username("Esai", "Thot", unique=True, prefix_len=2)  # esthot2, not esthot1
    u3 = user_factory(username=un3)

    assert un1 == "esthot", f"un1={un1}"
    assert un2 == "esthot", f"un2={un2}"
    assert un3 == "esthot2", f"un3={un3}"
    assert u1.username == "esthot", f"u1.username={u1.username}"
    assert u3.username == "esthot2", f"u3.username={u3.username}"


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
    res = split_name(raw)
    ref = (prefix, first, middle, last, suffix)
    assert res == ref, f"{ref} != {res} !"


@pytest.mark.parametrize(
    "user_id,output",
    [("TU-123", 123), ("TU-00123", 123), ("00123", 123), ("123", 123)],
)
def test_extract_id_num(user_id, output):
    res = extract_id_num(user_id)
    assert res == output, f"{res} != {output}"
