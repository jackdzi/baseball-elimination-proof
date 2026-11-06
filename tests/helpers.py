from __future__ import annotations

from pathlib import Path

from scripted_agent import judge
from slimconfig import build_output, plain_output

from contract import BoundInput, DivisionInput, EliminationOutput, PinOutput
from plugin import get_standings, pin_eliminations, subset_bound


def as_sandbox(value, cls):
    """A value as NanoAgent's verifier sandbox hands it over: rebuilt from its JSON."""
    return build_output(plain_output(value) if not isinstance(value, dict) else value, cls)


def task(seed: int = 7, teams: int = 6) -> DivisionInput:
    return build_output({"seed": seed, "teams": teams}, DivisionInput)


def gold_answer(given: DivisionInput, workspace: Path) -> dict:
    """A correct run's output through the real tools: get_standings, then subset_bound per certificate."""
    standings = plain_output(get_standings(given, workspace))

    def bound(team: str, subset: list[str]) -> dict:
        made = subset_bound(build_output({"task": plain_output(given), "team": team, "subset": subset}, BoundInput), workspace)
        return plain_output(made)

    return judge(standings, bound)


def gold_run(given: DivisionInput, workspace: Path) -> tuple[EliminationOutput, PinOutput]:
    output = as_sandbox(gold_answer(given, workspace), EliminationOutput)
    reference = as_sandbox(pin_eliminations(given, workspace), PinOutput)
    return output, reference
