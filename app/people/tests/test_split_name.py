import pytest

from app.people.utils import split_name


@pytest.mark.parametrize(
    "raw,prefix,first,middle,last,suffix",
    [
        ("Doc. Malik K. Kone,  Ph.D.", "Doc", "Malik", "K.", "Kone", "PhD"),
        ("Doc Kone  Ph.D.", "Doc", "", "", "Kone", "PhD"),
        ("Doc. M Kone,  Ph.D.", "Doc", "M.", "", "Kone", "PhD"),
        ("Blayon, O. G.", "", "O.", "G.", "Blayon", ""),
        ("Blayon O. G.", "", "O.", "G.", "Blayon", ""),
        ("A. J. K. Doe", "", "A.", "J. K.", "Doe", ""),
        ("Al J. K. Doe", "", "Al", "J. K.", "Doe", ""),
        ("Al Doe", "", "Al", "", "Doe", ""),
        ("Doe A.", "", "A.", "", "Doe", ""),
        ("B. Doe", "", "B.", "", "Doe", ""),
        ("Doe", "", "", "", "Doe", ""),
        (" Doc Oum", "Doc", "", "", "Oum", ""),
    ],
)
def test_split_name_initial_patterns(raw, prefix, first, middle, last, suffix):
    res = split_name(raw)
    ref = (prefix, first, middle, last, suffix)
    assert res == ref, f"{res} != {ref} !"
