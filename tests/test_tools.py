"""The tools, the independent oracle, and the MCP server."""

from __future__ import annotations

import os
import sys
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import anyio
import pytest
from helpers import task
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output, plain_output

from contract import BoundInput
from plugin import get_standings, pin_eliminations, subset_bound
from plugin.division import certificate, standings
from verifier.division import is_eliminated, rebuild

ROOT = Path(__file__).resolve().parents[1]


def division(names, wins, left, matrix) -> dict:
    """A hand-written division: ``left`` is each team's total games left, inside and outside."""
    outside = [left[i] - sum(matrix[i]) for i in range(len(names))]
    return {"names": names, "wins": wins, "losses": [0] * len(names), "outside": outside, "matrix": matrix}


# The classic four-team example (Sedgewick and Wayne): Montreal is out of reach of Atlanta on its own;
# Philadelphia can reach 83 wins, but Atlanta and New York share 6 more games: (83 + 78 + 6) / 2 = 83.5.
CLASSIC = division(
    ["Atlanta", "Philadelphia", "New York", "Montreal"],
    [83, 80, 78, 77],
    [8, 3, 6, 3],
    [[0, 1, 6, 1], [1, 0, 0, 2], [6, 0, 0, 0], [1, 2, 0, 0]],
)
# The 1996 AL East example: Detroit (best 76) is out only through all four rivals: (278 + 27) / 4 = 76.25.
AL_EAST = division(
    ["New York", "Baltimore", "Boston", "Toronto", "Detroit"],
    [75, 71, 69, 63, 49],
    [28, 28, 27, 27, 27],
    [[0, 3, 8, 7, 3], [3, 0, 2, 7, 4], [8, 2, 0, 0, 0], [7, 7, 0, 0, 0], [3, 4, 0, 0, 0]],
)


def brute_force(data: dict, x: int) -> bool:
    """Eliminated by the definition: some group of rivals beats x's best finish."""
    n = len(data["names"])
    best = data["wins"][x] + sum(data["matrix"][x]) + data["outside"][x]
    rivals = [i for i in range(n) if i != x]
    for size in range(1, n):
        for group in combinations(rivals, size):
            among = sum(data["matrix"][a][b] for a, b in combinations(group, 2))
            if Fraction(sum(data["wins"][i] for i in group) + among, size) > best:
                return True
    return False


def test_the_classic_example_is_decided_by_hand() -> None:
    assert certificate(CLASSIC, 0) is None
    assert certificate(CLASSIC, 1) == ["Atlanta", "New York"]
    assert certificate(CLASSIC, 2) is None
    assert certificate(CLASSIC, 3) == ["Atlanta"]
    assert [is_eliminated(CLASSIC, i) for i in range(4)] == [False, True, False, True]


def test_the_al_east_example_needs_all_four_rivals() -> None:
    assert certificate(AL_EAST, 4) == ["Baltimore", "Boston", "New York", "Toronto"]
    assert is_eliminated(AL_EAST, 4) is True
    assert not any(is_eliminated(AL_EAST, i) for i in range(4))


def test_the_tool_the_verifier_and_brute_force_agree_on_2000_divisions() -> None:
    for teams in range(4, 9):
        for seed in range(400):
            given = task(seed, teams)
            data = standings(given)
            assert data == rebuild(given)
            for x in range(teams):
                expected = brute_force(data, x)
                assert (certificate(data, x) is not None) == expected, (seed, teams, x)
                assert is_eliminated(data, x) == expected, (seed, teams, x)


def test_standings_are_consistent(tmp_path: Path) -> None:
    for seed in range(200):
        out = get_standings(task(seed, 8), tmp_path)
        assert [(-t.wins, t.name) for t in out.teams] == sorted((-t.wins, t.name) for t in out.teams)
        for row in out.teams:
            assert row.losses >= 0 and row.wins + row.losses + row.left_division + row.left_outside == 162
            assert row.left_division == sum(s.games for s in out.series if row.name in (s.team_a, s.team_b))


def test_subset_bound_gives_the_reduced_bound(tmp_path: Path) -> None:
    given = task(seed=3, teams=6)
    data = standings(given)
    names = data["names"]
    out = subset_bound(build_output({"task": plain_output(given), "team": names[0], "subset": names[1:4]}, BoundInput), tmp_path)
    bound = Fraction(out.bound_numerator, out.bound_denominator)
    assert bound == Fraction(out.subset_wins + out.games_among, 3)
    assert out.beats == (bound > out.team_max_wins)


@pytest.mark.parametrize("case", ["empty", "unknown", "self", "twice"])
def test_subset_bound_refuses_bad_groups(tmp_path: Path, case: str) -> None:
    given = task()
    names = standings(given)["names"]
    subset = {"empty": [], "unknown": ["Yankees"], "self": [names[0]], "twice": [names[1], names[1]]}[case]
    with pytest.raises(ValueError):
        subset_bound(build_output({"task": plain_output(given), "team": names[0], "subset": subset}, BoundInput), tmp_path)


def test_the_seeds_cover_every_kind_of_division(tmp_path: Path) -> None:
    kinds = set()
    for seed in range(100):
        given = task(seed, 6)
        data = standings(given)
        pin = pin_eliminations(given, tmp_path)
        if not pin.eliminated:
            kinds.add("none")
        for e in pin.eliminated:
            x = data["names"].index(e.team)
            best = data["wins"][x] + sum(data["matrix"][x]) + data["outside"][x]
            kinds.add("trivial" if any(w > best for w in data["wins"]) else "needs a group")
    assert kinds == {"none", "trivial", "needs a group"}


def test_the_mcp_server_lists_and_runs_every_tool(tmp_path: Path) -> None:
    async def run() -> None:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], cwd=str(ROOT), env={**os.environ, "NANOAGENT_WORKSPACE": str(tmp_path)}
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"get_standings", "subset_bound", "pin_eliminations"}
            given = {"seed": 1, "teams": 5}
            got = await session.call_tool("get_standings", given)
            assert not got.isError and len(got.structuredContent["teams"]) == 5
            team, rival = got.structuredContent["teams"][-1]["name"], got.structuredContent["teams"][0]["name"]
            bound = await session.call_tool("subset_bound", {"task": given, "team": team, "subset": [rival]})
            assert not bound.isError and "beats" in bound.structuredContent
            pinned = await session.call_tool("pin_eliminations", given)
            assert not pinned.isError
            bad = await session.call_tool("get_standings", {"seed": 1, "teams": 12})
            assert bad.isError

    anyio.run(run)
