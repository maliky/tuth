"""Generic fuzzy matching helpers."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Iterable, Tuple

logger = logging.getLogger(__name__)


def fuzzy_string_similarity(a: str, b: str) -> float:
    """Return a normalized similarity score in [0,1] between two strings."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def curriculum_similarity(
    token_a: str, token_b: str, threshold: float = 0.9
) -> Tuple[float, bool]:
    """Return (score, is_match) for curriculum-like strings."""
    score = fuzzy_string_similarity(token_a, token_b)
    return score, score >= threshold


def course_similarity(
    token_a: str, token_b: str, threshold: float = 0.9
) -> Tuple[float, bool]:
    """Return (score, is_match) for course-like strings."""
    score = fuzzy_string_similarity(token_a, token_b)
    return score, score >= threshold
