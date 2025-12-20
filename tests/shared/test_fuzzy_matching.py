import pytest

from app.shared.fuzzy_matching import name_similarity, top_name_matches


def test_name_similarity_handles_reordered_tokens():
    """Similarity should be high for reordered/normalized names."""
    a = "Abraham W. Harmon"
    b = "Harmon, Abraham W"
    sim = name_similarity(a, b)
    assert pytest.approx(sim, rel=0.01) == 1.0


def test_name_similarity_detects_differences():
    """Similarity should be low for unrelated names."""
    a = "Virginia Blyee"
    b = "Anthony Doe"
    sim = name_similarity(a, b)
    assert sim < 0.5


def test_top_name_matches_limit():
    """limit should cap the number of returned matches."""
    base = "john doe"
    cands = ["John Doe", "Jon Dough", "Jane Roe"]
    matches = top_name_matches(base, cands, limit=1)
    assert len(matches) == 1
    assert matches[0][0].lower().startswith("john")
