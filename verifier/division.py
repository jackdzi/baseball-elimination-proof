"""The baseball-elimination verifier. It rebuilds each division from its seed and decides every team
its own way: a depth-first augmenting-path maximum flow on an index matrix (the tools use a
breadth-first one on named nodes). Every certificate is checked by its inequality, with exact
fractions."""

from fractions import Fraction

from .checks import result
from .rng import Stream, canonical_sha256

MAX_SEED = 1_000_000_000
MIN_TEAMS, MAX_TEAMS = 4, 8
SEASON = 162
NAMES = (
    "Anglers", "Badgers", "Comets", "Drifters", "Ferrets", "Glaciers", "Herons", "Ironclads",
    "Jackals", "Kestrels", "Lanterns", "Moose", "Narwhals", "Otters", "Quarrymen", "Sandpipers",
)


def input_problem(task):
    if not 0 <= task.seed <= MAX_SEED:
        return f"seed must be from 0 to {MAX_SEED}"
    if not MIN_TEAMS <= task.teams <= MAX_TEAMS:
        return f"teams must be from {MIN_TEAMS} to {MAX_TEAMS}"
    return None


def rebuild(task):
    """The task's division, drawn exactly as the get_standings tool draws it (the same seeded stream)."""
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
                wins.append(min(leader, max(55, leader + stream.between(-1, 3) - left[i])))
        else:
            wins.append(leader - stream.between(0, 25))
    losses = [SEASON - wins[i] - left[i] for i in range(n)]
    return {"names": names, "wins": wins, "losses": losses, "outside": outside, "matrix": matrix}


def best_finish(data, x):
    return data["wins"][x] + sum(data["matrix"][x]) + data["outside"][x]


def flow_value(cap, source, sink):
    """The maximum flow of the capacity matrix ``cap`` (changed in place), by depth-first augmenting paths."""
    size = len(cap)
    total = 0
    while True:
        parent = [-1] * size
        parent[source] = source
        stack = [source]
        while stack and parent[sink] == -1:
            u = stack.pop()
            for v in range(size):
                if cap[u][v] > 0 and parent[v] == -1:
                    parent[v] = u
                    stack.append(v)
        if parent[sink] == -1:
            return total
        push, v = None, sink
        while v != source:
            room = cap[parent[v]][v]
            push = room if push is None else min(push, room)
            v = parent[v]
        v = sink
        while v != source:
            cap[parent[v]][v] -= push
            cap[v][parent[v]] += push
            v = parent[v]
        total += push


def is_eliminated(data, x):
    """Whether team x can no longer finish first or tied for first."""
    n = len(data["names"])
    best = best_finish(data, x)
    others = [i for i in range(n) if i != x]
    if any(data["wins"][i] > best for i in others):
        return True
    pairs = [(a, b) for a in others for b in others if a < b and data["matrix"][a][b] > 0]
    # Nodes: 0 source, 1 sink, then one per pair, then one per other team.
    size = 2 + len(pairs) + n
    cap = [[0] * size for _ in range(size)]
    needed = 0
    for k, (a, b) in enumerate(pairs):
        node = 2 + k
        cap[0][node] = data["matrix"][a][b]
        needed += data["matrix"][a][b]
        cap[node][2 + len(pairs) + a] = needed + 10_000
        cap[node][2 + len(pairs) + b] = needed + 10_000
    for i in others:
        cap[2 + len(pairs) + i][1] = best - data["wins"][i]
    return flow_value(cap, 0, 1) < needed


def certificate_problem(data, team, group):
    """Why ``group`` does not prove ``team`` eliminated, or None when it does."""
    index = {name: i for i, name in enumerate(data["names"])}
    if not group:
        return "the certificate is empty"
    unknown = [name for name in group if name not in index]
    if unknown:
        return f"the certificate names {unknown[0]!r}, no team of this division"
    if len(set(group)) != len(group):
        return "the certificate names a team twice"
    if team in group:
        return "the certificate holds the eliminated team itself"
    members = [index[name] for name in group]
    wins = sum(data["wins"][i] for i in members)
    among = sum(data["matrix"][a][b] for a in members for b in members if a < b)
    bound = Fraction(wins + among, len(members))
    best = best_finish(data, index[team])
    if not bound > best:
        return f"its bound ({wins} + {among}) / {len(members)} = {bound} is not greater than {team}'s best finish, {best}"
    return None


def team_problem(data, name):
    if name not in data["names"]:
        return f"no team named {name!r} in this division"
    return None


def verify_division_input(value):
    problem = input_problem(value)
    return result(False, problem) if problem else result(True, "input is valid")


def verify_bound_input(value):
    problem = input_problem(value.task)
    if problem:
        return result(False, problem)
    data = rebuild(value.task)
    for name in [value.team, *value.subset]:
        if team_problem(data, name):
            return result(False, team_problem(data, name), teams=sorted(data["names"]))
    if not value.subset:
        return result(False, "the subset needs at least one team")
    if len(set(value.subset)) != len(value.subset):
        return result(False, "the subset names a team twice")
    if value.team in value.subset:
        return result(False, "the subset may not hold the team being tested")
    return result(True, "input is valid")


def verify_standings_output(task, output):
    data = rebuild(task)
    n = len(data["names"])
    rows = {row.name: row for row in output.teams}
    if sorted(rows) != sorted(data["names"]) or len(output.teams) != n:
        return result(False, "the teams are not the seed's")
    for i, name in enumerate(data["names"]):
        row = rows[name]
        expected = (data["wins"][i], data["losses"][i], sum(data["matrix"][i]), data["outside"][i], best_finish(data, i))
        if (row.wins, row.losses, row.left_division, row.left_outside, row.max_wins) != expected:
            return result(False, f"{name}'s row is not the seed's")
    games = {}
    for series in output.series:
        games[frozenset((series.team_a, series.team_b))] = series.games
    expected_games = {
        frozenset((data["names"][a], data["names"][b])): data["matrix"][a][b]
        for a in range(n)
        for b in range(a + 1, n)
        if data["matrix"][a][b]
    }
    if games != expected_games or len(output.series) != len(expected_games):
        return result(False, "the games left between teams are not the seed's")
    return result(True, "the standings are the seed's")


def verify_bound_output(given, output):
    data = rebuild(given.task)
    index = {name: i for i, name in enumerate(data["names"])}
    members = [index[name] for name in given.subset]
    wins = sum(data["wins"][i] for i in members)
    among = sum(data["matrix"][a][b] for a in members for b in members if a < b)
    bound = Fraction(wins + among, len(members))
    best = best_finish(data, index[given.team])
    got = (output.team_max_wins, output.subset_wins, output.games_among, output.bound_numerator, output.bound_denominator)
    if got != (best, wins, among, bound.numerator, bound.denominator) or output.beats != (bound > best):
        return result(False, "the bound is not what the standings give")
    return result(True, "the bound is right")


def truth(data):
    return {name: is_eliminated(data, i) for i, name in enumerate(data["names"])}


def verify_pin_output(task, output):
    data = rebuild(task)
    if output.standings_sha256 != canonical_sha256(data):
        return result(False, "the pinned standings are not the seed's")
    out = truth(data)
    if sorted(e.team for e in output.eliminated) != sorted(k for k, v in out.items() if v):
        return result(False, "the pinned eliminations disagree with the verifier's maximum flow")
    if sorted(output.alive) != sorted(k for k, v in out.items() if not v):
        return result(False, "the pinned alive teams disagree with the verifier's maximum flow")
    for e in output.eliminated:
        problem = certificate_problem(data, e.team, e.certificate)
        if problem:
            return result(False, f"the pinned certificate for {e.team} fails: {problem}")
    return result(True, "the answer key is the division's eliminations", eliminated=len(output.eliminated))


def verify_task(arguments, output, reference, workspace):
    data = rebuild(arguments)
    if reference is None or verify_pin_output(arguments, reference)["valid"] is not True:
        return result(False, "the pinned answer key does not match the division the seed gives")
    out = truth(data)
    names = data["names"]
    claims = {}
    problems = []
    for e in output.eliminated:
        claims.setdefault(e.team, []).append(("eliminated", e.certificate))
    for name in output.alive:
        claims.setdefault(name, []).append(("alive", None))
    unknown = sorted(name for name in claims if name not in names)
    twice = sorted(name for name, said in claims.items() if name in names and len(said) > 1)
    unjudged = sorted(name for name in names if name not in claims)
    verdicts = {}
    for name in names:
        said = claims.get(name, [])
        if len(said) != 1:
            verdicts[name] = "not judged exactly once"
            continue
        kind, group = said[0]
        if kind == "alive":
            verdicts[name] = "correct" if not out[name] else "eliminated, but submitted as alive"
        elif not out[name]:
            verdicts[name] = "alive, but submitted as eliminated"
        else:
            problem = certificate_problem(data, name, group)
            verdicts[name] = "correct" if problem is None else f"eliminated, but its certificate fails: {problem}"
    correct = sum(1 for v in verdicts.values() if v == "correct")
    score = correct / len(names)
    if unknown:
        problems.append("unknown teams: " + ", ".join(unknown))
    if twice:
        problems.append("judged more than once: " + ", ".join(twice))
    if unjudged:
        problems.append("never judged: " + ", ".join(unjudged))
    problems += [f"{name}: {v}" for name, v in sorted(verdicts.items()) if v != "correct" and name not in twice + unjudged]
    details = {
        "teams": len(names),
        "teams_correct": correct,
        "eliminated_expected": sorted(k for k, v in out.items() if v),
        "eliminated_submitted": sorted(e.team for e in output.eliminated),
        "per_team": verdicts,
        "unknown_teams": unknown,
    }
    if problems:
        return result(False, "; ".join(problems), score=score, **details)
    return result(True, f"all {len(names)} teams are judged correctly, every elimination with a valid certificate", **details)
