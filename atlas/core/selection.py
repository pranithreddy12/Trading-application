"""
selection.py — Evolutionary tournament selection utilities.

Provides robust selection mechanisms that balance exploration vs exploitation
when choosing strategies for promotion, combination, or mutation.

Tournament selection is much more robust than:
- Pure fitness-proportional (outlier scores dominate)
- Fixed top-N (score 34.5 vs 34.4 = essentially random choice)
"""

import random
from typing import Any, Callable


def tournament_select(
    candidates: list[dict],
    tournament_size: int = 5,
    key: str | Callable[[dict], float] = "composite_fitness",
    n_select: int = 1,
) -> list[dict]:
    """
    Pick candidates using tournament selection.

    For each selection, randomly sample `tournament_size` candidates
    and return the one with the highest score.

    Parameters
    ----------
    candidates : list[dict]
        Pool of candidates to select from.
    tournament_size : int
        Number of candidates in each tournament. Larger = more exploitation.
        Default 5 provides a good exploration/exploitation balance.
    key : str or callable
        If str, the dict key to use as the fitness score.
        If callable, a function that takes a dict and returns a float score.
    n_select : int
        Number of selections to make (with replacement).

    Returns
    -------
    list[dict]
        Selected candidates (in order of selection).

    Examples
    --------
    >>> strategies = [{"name": "a", "score": 10}, {"name": "b", "score": 20}]
    >>> selected = tournament_select(strategies, tournament_size=2, key="score")
    """
    if not candidates:
        return []

    # Resolve key to a callable scorer
    if isinstance(key, str):
        _key_name = key

        def _scorer(s: dict) -> float:
            return float(s.get(_key_name, 0) or 0)
    else:
        _scorer = key

    # If pool is smaller than tournament, just take the best
    if len(candidates) <= tournament_size:
        sorted_candidates = sorted(candidates, key=_scorer, reverse=True)
        return sorted_candidates[:n_select]

    selected: list[dict] = []
    for _ in range(n_select):
        tournament = random.sample(candidates, tournament_size)
        winner = max(tournament, key=_scorer)
        selected.append(winner)

    return selected


def tournament_select_unique(
    candidates: list[dict],
    tournament_size: int = 5,
    key: str | Callable[[dict], float] = "composite_fitness",
    n_select: int = 1,
    id_key: str = "id",
) -> list[dict]:
    """
    Same as tournament_select but ensures no duplicate selections.
    Uses id_key to track uniqueness.

    Useful when you need N distinct candidates (e.g., N parent pairs).
    """
    if not candidates:
        return []

    # Resolve key to a callable scorer
    if isinstance(key, str):
        _key_name = key

        def _scorer(s: dict) -> float:
            return float(s.get(_key_name, 0) or 0)
    else:
        _scorer = key

    if len(candidates) <= tournament_size:
        sorted_candidates = sorted(candidates, key=_scorer, reverse=True)
        return sorted_candidates[:n_select]

    selected: list[dict] = []
    selected_ids: set[str] = set()
    pool = list(candidates)

    for _ in range(n_select):
        if len(pool) < tournament_size:
            break

        tournament = random.sample(pool, tournament_size)
        winner = max(tournament, key=_scorer)
        winner_id = str(winner.get(id_key, ""))
        selected.append(winner)
        selected_ids.add(winner_id)
        # Remove winner from pool for next round
        pool = [c for c in pool if str(c.get(id_key, "")) != winner_id]

    return selected
