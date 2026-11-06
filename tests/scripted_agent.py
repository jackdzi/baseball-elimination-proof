"""A scripted stand-in for the agent: it follows the task's instructions with no model, so a whole
run can be replayed offline. It reads only what get_standings returns, and confirms every
certificate with a subset_bound call before it submits it."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations


def find_certificate(standings: dict, team: str) -> list[str] | None:
    """The smallest group of rivals whose bound beats ``team``'s best finish, or None."""
    rows = {row["name"]: row for row in standings["teams"]}
    games = {frozenset((s["team_a"], s["team_b"])): s["games"] for s in standings["series"]}
    best = rows[team]["max_wins"]
    rivals = sorted((name for name in rows if name != team), key=lambda name: (-rows[name]["wins"], name))
    for size in range(1, len(rivals) + 1):
        for group in combinations(rivals, size):
            among = sum(games.get(frozenset(pair), 0) for pair in combinations(group, 2))
            if Fraction(sum(rows[name]["wins"] for name in group) + among, size) > best:
                return list(group)
    return None


def judge(standings: dict, bound) -> dict:
    """The task's output. ``bound(team, subset)`` calls subset_bound and returns its output as a dict."""
    eliminated, alive = [], []
    for row in standings["teams"]:
        group = find_certificate(standings, row["name"])
        if group is None:
            alive.append(row["name"])
            continue
        if not bound(row["name"], group)["beats"]:
            raise AssertionError(f"subset_bound does not confirm the certificate for {row['name']}")
        eliminated.append({"team": row["name"], "certificate": group})
    return {"eliminated": eliminated, "alive": alive}
