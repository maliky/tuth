"""Tests for curriculum the academic curriculum model."""

import pytest

from app.academics.models.curriculum import Curriculum

pytestmark = pytest.mark.django_db


def test_curriculum_get_or_create_respects_fuzzy_threshold(college_factory):
    """Fuzzy threshold reuses near-duplicates; default (1.0) creates new."""
    college = college_factory("FUZC")
    base, _ = Curriculum.objects.get_or_create(
        short_name="BSCS",
        college=college,
        defaults={"long_name": "Bachelor of Computer Science"},
    )

    reuse, created = Curriculum.objects.get_or_create(
        short_name="BSC Computer Sci",
        college=college,
        defaults={"long_name": "Computer Science"},
        fuzzy_threshold=0.8,
    )
    assert reuse.id == base.id
    assert created is False

    new_cur, created_strict = Curriculum.objects.get_or_create(
        short_name="BSCS-ALT",
        college=college,
        defaults={"long_name": "Computer Science Alt"},
        # default fuzzy_threshold=1.0 => strict
    )
    assert created_strict is True
    assert new_cur.id != base.id
