"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_STANDINGS = "get_standings"
    SUBSET_BOUND = "subset_bound"
    PIN_ELIMINATIONS = "pin_eliminations"


class Task(Enum):
    FIND_ELIMINATED = "find-eliminated"


TEAM = "A team's name, exactly as get_standings gives it, e.g. Otters"
TASK = "The task input, copied exactly as given"


@dataclass
class DivisionInput(Output):
    seed: Annotated[int, "Which division: any integer from 0 to 1000000000; the same seed always gives the same standings"]
    teams: Annotated[int, "How many teams the division has, from 4 to 8"]


@dataclass
class TeamRow(Output):
    name: Annotated[str, TEAM]
    wins: Annotated[int, "Games won so far"]
    losses: Annotated[int, "Games lost so far"]
    left_division: Annotated[int, "Games left against the other teams of this division"]
    left_outside: Annotated[int, "Games left against teams outside this division"]
    max_wins: Annotated[int, "The most wins it can still reach: wins plus every game it has left"]


@dataclass
class Series(Output):
    team_a: Annotated[str, TEAM]
    team_b: Annotated[str, TEAM]
    games: Annotated[int, "Games the two teams still play against each other, at least 1"]


@dataclass
class StandingsOutput(Output):
    teams: Annotated[list[TeamRow], "Every team of the division, most wins first, ties by name"]
    series: Annotated[list[Series], "Every pair of teams that still play each other, with how many games"]


@dataclass
class BoundInput(Output):
    task: Annotated[DivisionInput, TASK]
    team: Annotated[str, "The team whose chances are tested"]
    subset: Annotated[list[Annotated[str, TEAM]], "One or more other teams, the group R tested against it, each once"]


@dataclass
class BoundOutput(Output):
    team: Annotated[str, "The team tested"]
    team_max_wins: Annotated[int, "The team's wins plus every game it has left"]
    subset: Annotated[list[str], "The group R, as given"]
    subset_wins: Annotated[int, "The wins of R's teams added together"]
    games_among: Annotated[int, "The games R's teams still play against each other"]
    bound_numerator: Annotated[int, "(subset_wins + games_among) / |R| as a reduced fraction: its numerator"]
    bound_denominator: Annotated[int, "That fraction's denominator"]
    beats: Annotated[bool, "true when the bound is strictly greater than team_max_wins"]


@dataclass
class Elimination(Output):
    team: Annotated[str, "An eliminated team"]
    certificate: Annotated[
        list[Annotated[str, TEAM]],
        "The group R that proves it: other teams whose (wins + games among them) / |R| is greater than its max_wins",
    ]


@dataclass
class EliminationOutput(Output):
    eliminated: Annotated[list[Elimination], "Every mathematically eliminated team, each with its certificate"]
    alive: Annotated[list[Annotated[str, TEAM]], "Every team that can still finish first or tied for first"]


@dataclass
class PinOutput(Output):
    standings_sha256: Annotated[str, "sha256 of the standings as canonical JSON"]
    eliminated: Annotated[list[Elimination], "Every eliminated team, with the certificate its minimum cut gives"]
    alive: Annotated[list[str], "Every team that is not eliminated"]


TOOLS = {
    Tool.GET_STANDINGS: (DivisionInput, StandingsOutput),
    Tool.SUBSET_BOUND: (BoundInput, BoundOutput),
    Tool.PIN_ELIMINATIONS: (DivisionInput, PinOutput),
}
TASKS = {Task.FIND_ELIMINATED: (DivisionInput, EliminationOutput)}
