import pytest

from app.people.utils import split_name


@pytest.mark.parametrize(
    "raw,prefix,first,middle,last,suffix",
    [
        ("Prof. Isaac A. B. Yancy Ph.D.", "Prof", "Isaac", "A. B.", "Yancy", "PhD"),
        ("Blayon, O. G.", "", "O", "G", "Blayon", ""),
        ("A. J. K. Doe", "", "A", "J. K.", "Doe", ""),
    ],
)
def test_split_name_initial_patterns(raw, prefix, first, middle, last, suffix):
    assert split_name(raw) == (prefix, first, middle, last, suffix)
