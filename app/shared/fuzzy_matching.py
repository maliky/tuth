"""Generic fuzzy matching helpers for names, courses, and curricula."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, List, Sequence, Tuple, TypeVar

from rapidfuzz.distance import JaroWinkler

from app.people.utils import canonicalize_name

Score = float
_T = TypeVar("_T")


def identity(value: Any) -> Any:
    """Simple identity helper usable as a default token function."""
    return value


def similarity_ratio(a: str, b: str) -> float:
    """Lightweight fuzzy ratio in [0,1]."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def sim_jarowinkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """A fuzzy distance for names."""
    return float(JaroWinkler.normalized_distance(a, b, prefix_weight=prefix_weight))


def token_similarity(
    token_a: str, token_b: str, threshold: float = 0.9
) -> Tuple[float, bool]:
    """Return (score, is_match) for course/curriculum-like strings."""
    score = similarity_ratio(token_a, token_b)
    return score, score >= threshold


# ------- Name-specific similarity -------
def normalize_tokens(name: str) -> Tuple[str, list[str]]:
    """Return (surname, given_tokens) lowercased and stripped of punctuation."""
    tokens = [re.sub(r"[^A-Za-z]", "", part).lower() for part in name.split() if part]
    if not tokens:
        return "", []

    surn = tokens[-1]
    givens = tokens[:-1]
    return surn, givens


def top_name_matches(
    base: str,
    candidates: Iterable[_T],
    token_fn: Callable[[_T], str] = identity,
    threshold: float = 0.9,
    top_n: int = 3,
) -> list[tuple[_T, float]]:
    """Return up to 'limit' candidates ordered by similarity >= threshold.

    token_fn :  is a function taking a candidate and return a str to compare with base.
    """
    scored: list[tuple[_T, float]] = []
    for cand in candidates:
        token = token_fn(cand)
        score = name_similarity(base, token)
        if score >= threshold:
            scored.append((cand, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_n]


def best_name_match(
    base: str,
    candidates: Iterable[_T],
    token_fn: Callable[[_T], str],
    threshold: float = 0.9,
) -> tuple[_T | None, float]:
    """Return the best candidate and score meeting the threshold."""
    ranked = top_name_matches(
        base, candidates, token_fn=token_fn, threshold=threshold, top_n=1
    )
    return ranked[0] if ranked else (None, 0.0)


def best_matches(
    ss_username: str,
    tusis_usernames: Iterable[str],
    *,
    top_n: int = 2,
    max_gap: float = 0.2,
) -> List[Tuple[str, Score]]:
    """Return the best Tusis username candidates for a SmartSchool username.

    Always returns the top candidate (if any). Includes a second when its score
    is within *max_gap* of the first. Scores are similarity values where
    1.0 == identical and 0 == no match.
    """
    scores = top_name_matches(ss_username, tusis_usernames, top_n=top_n)

    if not scores:
        return []

    best = scores[0]
    if top_n < 2 or len(scores) < 2:
        return [best]

    second = scores[1]
    if best[1] - second[1] <= max_gap:
        return [best, second]
    return [best]


def name_similarity(
    name_a: str,
    name_b: str,
    sim_threshold: float = 0.8,
    weight_surname: float = 0.7,
    length_penalty: float = 0.07,
) -> float:
    """Greedy symmetric similarity between two names in [0,1].

    Surnames dominate; given names allow initials/full swaps.
    """

    surn_a, givens_a = normalize_tokens(canonicalize_name(name_a))
    surn_b, givens_b = normalize_tokens(canonicalize_name(name_b))

    sim_surname = sim_jarowinkler(surn_a, surn_b)

    if sim_surname < sim_threshold:
        return sim_surname * 0.2

    if not givens_a and not givens_b:
        sim_given = 1.0
    else:
        given_a = " ".join(givens_a)
        given_b = " ".join(givens_b)
        sim_given = sim_jarowinkler(given_a, given_b)

    sim = weight_surname * sim_surname + (1 - weight_surname) * sim_given
    return max(0.0, min(1.0, sim))
