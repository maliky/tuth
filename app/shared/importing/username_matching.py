"""Username matching helpers between SmartSchool and Tusis users."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from rapidfuzz.distance import JaroWinkler

Score = float


def username_similarity(left: str | None, right: str | None) -> Score:
    """Return similarity in [0,1] between two usernames using Jaro-Winkler."""
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return 0.0
    distance = JaroWinkler.normalized_distance(a, b)
    return 1.0 - float(distance)


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
        score = username_similarity(ss_username, username)
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
