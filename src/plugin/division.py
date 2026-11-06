"""The divisions, their eliminations by maximum flow, and the three tools."""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from pathlib import Path

from contract import (
    BoundInput,
    BoundOutput,
    DivisionInput,
    Elimination,
    PinOutput,
    Series,
    StandingsOutput,
    TeamRow,
)
from plugin.rng import Stream, canonical_sha256

MAX_SEED = 1_000_000_000
MIN_TEAMS, MAX_TEAMS = 4, 8
SEASON = 162
NAMES = (
    "Anglers", "Badgers", "Comets", "Drifters", "Ferrets", "Glaciers", "Herons", "Ironclads",
    "Jackals", "Kestrels", "Lanterns", "Moose", "Narwhals", "Otters", "Quarrymen", "Sandpipers",
)


def standings(task: DivisionInput) -> dict:
    """The task's division as plain data: names, wins, losses, outside games left, and the matrix of
    games left between division teams.

    Two seeds in ten are a tight race. Five have a block of 2 or 3 contenders close in wins with many
    games left among themselves, while every other team can still pass the leader on its own: there
    an elimination needs a group of teams to prove it. Three are spread wide, where a team is often
    out of reach of a single rival."""
    if not 0 <= task.seed <= MAX_SEED:
        raise ValueError(f"seed must be from 0 to {MAX_SEED}")
    if not MIN_TEAMS <= task.teams <= MAX_TEAMS:
        raise ValueError(f"teams must be from {MIN_TEAMS} to {MAX_TEAMS}")
    n = task.teams
    stream = Stream("baseball", f"{task.seed}|{n}")
    names = stream.shuffled(NAMES)[:n]
    style = stream.below(10)
    block = stream.between(2, 3) if 2 <= style < 7 else 0
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            games = stream.between(4, 7) if j < block else 0 if stream.chance(1, 5) else stream.between(1, 7)
            matrix[i][j] = matrix[j][i] = games
    outside = [stream.between(0, 6) for _ in range(n)]
    left = [sum(matrix[i]) + outside[i] for i in range(n)]
    leader = stream.between(80, 96)
    wins = []
    for i in range(n):
        if i == 0:
            wins.append(leader)
        elif style < 2:
            wins.append(leader - stream.between(0, 3))
        elif style < 7:
            if i < block:
                wins.append(leader - stream.between(0, 3))
            else:
                # Its best finish lands from 1 short of the leader's wins to 3 past them.
                wins.append(min(leader, max(55, leader + stream.between(-1, 3) - left[i])))
        else:
            wins.append(leader - stream.between(0, 25))
    losses = [SEASON - wins[i] - left[i] for i in range(n)]
    return {"names": names, "wins": wins, "losses": losses, "outside": outside, "matrix": matrix}


def max_flow(capacity: dict[str, dict[str, int]], source: str, sink: str) -> tuple[int, set[str]]:
    """Edmonds-Karp: the maximum flow, and the nodes the source still reaches in the residual graph."""
    residual = {u: dict(edges) for u, edges in capacity.items()}
    for u, edges in capacity.items():
        for v in edges:
            residual.setdefault(v, {}).setdefault(u, 0)
    flow = 0
    while True:
        parent = {source: source}
        queue = deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v, room in residual[u].items():
                if room > 0 and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            return flow, set(parent)
        path, v = [], sink
        while v != source:
            path.append((parent[v], v))
            v = parent[v]
        push = min(residual[u][v] for u, v in path)
        for u, v in path:
            residual[u][v] -= push
            residual[v][u] += push
        flow += push


def certificate(data: dict, x: int) -> list[str] | None:
    """A group of teams proving team x is eliminated, or None when it is not."""
    names, wins, matrix = data["names"], data["wins"], data["matrix"]
    n = len(names)
    best = wins[x] + sum(matrix[x]) + data["outside"][x]
    others = [i for i in range(n) if i != x]
    beyond = [i for i in others if wins[i] > best]
    if beyond:
        top = min(beyond, key=lambda i: (-wins[i], names[i]))
        return [names[top]]
    capacity: dict[str, dict[str, int]] = {"s": {}}
    total = 0
    unlimited = sum(sum(row) for row in matrix) + 1
    for a in others:
        capacity[f"t{a}"] = {"t": best - wins[a]}
        for b in others:
            if a < b and matrix[a][b]:
                capacity["s"][f"g{a}-{b}"] = matrix[a][b]
                capacity[f"g{a}-{b}"] = {f"t{a}": unlimited, f"t{b}": unlimited}
                total += matrix[a][b]
    flow, reached = max_flow(capacity, "s", "t")
    if flow == total:
        return None
    return sorted(names[i] for i in others if f"t{i}" in reached)


def eliminations(data: dict) -> tuple[list[Elimination], list[str]]:
    out, alive = [], []
    for x, name in enumerate(data["names"]):
        proof = certificate(data, x)
        if proof is None:
            alive.append(name)
        else:
            out.append(Elimination(team=name, certificate=proof))
    return sorted(out, key=lambda e: e.team), sorted(alive)


def get_standings(task: DivisionInput, workspace: Path) -> StandingsOutput:
    data = standings(task)
    names, wins, matrix = data["names"], data["wins"], data["matrix"]
    order = sorted(range(len(names)), key=lambda i: (-wins[i], names[i]))
    teams = [
        TeamRow(
            name=names[i],
            wins=wins[i],
            losses=data["losses"][i],
            left_division=sum(matrix[i]),
            left_outside=data["outside"][i],
            max_wins=wins[i] + sum(matrix[i]) + data["outside"][i],
        )
        for i in order
    ]
    series = [
        Series(team_a=names[a], team_b=names[b], games=matrix[a][b])
        for p, a in enumerate(order)
        for b in order[p + 1 :]
        if matrix[a][b]
    ]
    return StandingsOutput(teams=teams, series=series)


def subset_bound(given: BoundInput, workspace: Path) -> BoundOutput:
    data = standings(given.task)
    index = {name: i for i, name in enumerate(data["names"])}
    unknown = [name for name in [given.team, *given.subset] if name not in index]
    if unknown:
        raise ValueError(f"no team named {unknown[0]!r} in this division; the teams are {', '.join(sorted(index))}")
    if not given.subset:
        raise ValueError("the subset needs at least one team")
    if len(set(given.subset)) != len(given.subset):
        raise ValueError("the subset names a team twice")
    if given.team in given.subset:
        raise ValueError("the subset may not hold the team being tested")
    group = [index[name] for name in given.subset]
    x = index[given.team]
    best = data["wins"][x] + sum(data["matrix"][x]) + data["outside"][x]
    subset_wins = sum(data["wins"][i] for i in group)
    among = sum(data["matrix"][a][b] for a in group for b in group if a < b)
    bound = Fraction(subset_wins + among, len(group))
    return BoundOutput(
        team=given.team,
        team_max_wins=best,
        subset=list(given.subset),
        subset_wins=subset_wins,
        games_among=among,
        bound_numerator=bound.numerator,
        bound_denominator=bound.denominator,
        beats=bound > best,
    )


def pin_eliminations(task: DivisionInput, workspace: Path) -> PinOutput:
    data = standings(task)
    eliminated, alive = eliminations(data)
    return PinOutput(standings_sha256=canonical_sha256(data), eliminated=eliminated, alive=alive)
