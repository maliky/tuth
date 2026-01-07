"""Generic fuzzy matching helpers for names, courses, and curricula."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, List, Sequence, Tuple, TypeVar

from rapidfuzz.distance import JaroWinkler

Score = float
_T = TypeVar("_T")


def identity(value: Any) -> Any:
    """Simple identity helper usable as a default token function."""
    return value


def jarowinkler_similarity(left: str | None, right: str | None) -> Score:
    """Return similarity in [0,1] between two usernames using Jaro-Winkler."""
    if not left or not right:
        return 0.0
    distance = JaroWinkler.normalized_distance(left, right)
    return 1.0 - float(distance)


def seq_similarity_score(left: str, right: str) -> float:
    """Lightweight fuzzy ratio in [0,1]."""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def token_similarity(
    token_a: str, token_b: str, threshold: float = 0.9
) -> Tuple[float, bool]:
    """Return (score, is_match) for course/curriculum-like strings."""
    score = jarowinkler_similarity(token_a, token_b)
    return score, score >= threshold


def normalize_name_tokens(name: str) -> Tuple[str, list[str]]:
    """Return (surname, given_tokens) lowercased and stripped of punctuation."""
    tokens = [re.sub(r"[^A-Za-z]", "", part).lower() for part in name.split() if part]
    if not tokens:
        return "", []

    surn = tokens[-1]
    givens = tokens[:-1]
    return surn, givens


def sim_name_token(x: str, y: str) -> float:
    """Similarity between two given-name tokens, handling initials."""
    if not x or not y:
        return 0.0
    if len(x) == 1 and len(y) == 1:
        return 1.0 if x == y else 0.2
    if len(x) == 1 and len(y) > 1:
        return 0.9 if x == y[0] else 0.1
    if len(y) == 1 and len(x) > 1:
        return 0.9 if y == x[0] else 0.1
    return seq_similarity_score(x, y)


def name_similarity(
    name_a: str,
    name_b: str,
    sim_threshold: float = 0.8,
    weight_surname: float = 0.6,
    length_penalty: float = 0.07,
) -> float:
    """Greedy symmetric similarity between two names in [0,1].

    Surnames dominate; given names allow initials/full swaps.
    """

    surn_a, givens_a = normalize_name_tokens(name_a)
    surn_b, givens_b = normalize_name_tokens(name_b)

    sim_surname = jarowinkler_similarity(surn_a, surn_b)

    # > Why do we reduce the case of low sim_threshold ?
    # > to make it more apparant that there is not similarity ?
    if sim_surname < sim_threshold:
        return sim_surname * 0.2

    if not givens_a and not givens_b:
        sim_given = 1.0
    else:
        scores_a = [
            max((sim_name_token(x, y) for y in givens_b), default=0.0) for x in givens_a
        ]
        scores_b = [
            max((sim_name_token(y, x) for x in givens_a), default=0.0) for y in givens_b
        ]
        avg_a = sum(scores_a) / len(scores_a) if scores_a else 0.0
        avg_b = sum(scores_b) / len(scores_b) if scores_b else 0.0
        sim_given_raw = (avg_a + avg_b) / 2
        penalty = length_penalty * abs(len(givens_a) - len(givens_b))
        sim_given = max(0.0, sim_given_raw - penalty)

    sim = weight_surname * sim_surname + (1 - weight_surname) * sim_given
    return max(0.0, min(1.0, sim))


def top_name_matches(
    base: str,
    candidates: Iterable[_T],
    token_fn: Callable[[_T], str] = identity,
    threshold: float = 0.9,
    limit: int = 3,
) -> list[tuple[_T, float]]:
    """Return up to 'limit' candidates ordered by similarity >= threshold."""

    scored: list[tuple[_T, float]] = []
    
    for cand in candidates:
        token = token_fn(cand)
        score = name_similarity(base, token)
        if score >= threshold:
            scored.append((cand, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:limit]


def best_name_match(
    base: str,
    candidates: Iterable[_T],
    token_fn: Callable[[_T], str],
    threshold: float = 0.9,
) -> tuple[_T | None, float]:
    """Return the best candidate and score meeting the threshold."""
    ranked = top_name_matches(
        base, candidates, token_fn=token_fn, threshold=threshold, limit=1
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
    scores: list[tuple[str, Score]] = []
    for username in tusis_usernames:
        score = jarowinkler_similarity(ss_username, username)
        scores.append((username, score))
    scores.sort(key=lambda item: item[1], reverse=True)

    if not scores:
        return []

    best = scores[0]
    if top_n < 2 or len(scores) < 2:
        return [best]

    second = scores[1]
    if best[1] - second[1] <= max_gap:
        return [best, second]
    return [best]
