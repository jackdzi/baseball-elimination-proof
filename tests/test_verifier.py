"""The verifier on correct, wrong, missing, malformed and boundary results."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import as_sandbox, gold_answer, gold_run, task
from slimconfig import build_output, plain_output

import verifier
from contract import BoundInput, EliminationOutput, PinOutput, StandingsOutput
from plugin import get_standings, pin_eliminations, subset_bound
from plugin.division import standings

TASK = "find-eliminated"


def best(data: dict, i: int) -> int:
    return data["wins"][i] + sum(data["matrix"][i]) + data["outside"][i]


def find(teams: int, predicate) -> int:
    """The first seed whose division, with ``teams`` teams, has the case ``predicate(task)`` tests."""
    for seed in range(2000):
        if predicate(task(seed, teams)):
            return seed
    raise AssertionError("no seed has the case")


def nontrivial(given) -> bool:
    """Some team is eliminated although no single rival has more wins than its best finish."""
    data = standings(given)
    names = data["names"]
    return any(
        not any(data["wins"][j] > best(data, names.index(e.team)) for j in range(len(names)))
        for e in pin_eliminations(given, Path(".")).eliminated
    )


def judge(given, answer: dict, workspace: Path) -> dict:
    reference = as_sandbox(pin_eliminations(given, workspace), PinOutput)
    return verifier.verify_task(TASK, given, as_sandbox(answer, EliminationOutput), reference, str(workspace))


def test_accepts_a_correct_answer(tmp_path: Path) -> None:
    given = task(seed=find(6, nontrivial), teams=6)
    output, reference = gold_run(given, tmp_path)
    verdict = verifier.verify_task(TASK, given, output, reference, str(tmp_path))
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict["message"]


@pytest.mark.parametrize("teams", [4, 5, 6, 7, 8])
@pytest.mark.parametrize("seed", range(25))
def test_accepts_correct_answers_whose_certificates_differ_from_the_key(tmp_path: Path, teams: int, seed: int) -> None:
    # The scripted agent submits the smallest certificate, often not the minimum cut's: any valid one passes.
    given = task(seed, teams)
    output, reference = gold_run(given, tmp_path)
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is True


def test_rejects_an_eliminated_team_submitted_as_alive(tmp_path: Path) -> None:
    given = task(seed=find(6, nontrivial), teams=6)
    answer = gold_answer(given, tmp_path)
    moved = answer["eliminated"].pop()
    answer["alive"].append(moved["team"])
    verdict = judge(given, answer, tmp_path)
    assert verdict["valid"] is False and verdict["score"] == pytest.approx(5 / 6)
    assert verdict["details"]["per_team"][moved["team"]] == "eliminated, but submitted as alive"


def test_rejects_an_alive_team_submitted_as_eliminated(tmp_path: Path) -> None:
    given = task(seed=7, teams=6)
    answer = gold_answer(given, tmp_path)
    team = answer["alive"].pop()
    answer["eliminated"].append({"team": team, "certificate": [answer["alive"][0] if answer["alive"] else answer["eliminated"][0]["team"]]})
    verdict = judge(given, answer, tmp_path)
    assert verdict["valid"] is False
    assert verdict["details"]["per_team"][team] == "alive, but submitted as eliminated"


def test_rejects_a_certificate_whose_bound_does_not_beat(tmp_path: Path) -> None:
    given = task(seed=find(6, nontrivial), teams=6)
    answer = gold_answer(given, tmp_path)
    data = standings(given)
    target = next(e for e in answer["eliminated"] if len(e["certificate"]) > 1)
    weakest = min((n for n in data["names"] if n != target["team"]), key=lambda n: data["wins"][data["names"].index(n)])
    target["certificate"] = [weakest]
    verdict = judge(given, answer, tmp_path)
    assert verdict["valid"] is False
    assert "certificate fails" in verdict["details"]["per_team"][target["team"]]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda e: [e["team"], *e["certificate"]], "the eliminated team itself"),
        (lambda e: [*e["certificate"], "Yankees"], "no team of this division"),
        (lambda e: [*e["certificate"], e["certificate"][0]], "a team twice"),
        (lambda e: [], "empty"),
    ],
)
def test_rejects_malformed_certificates(tmp_path: Path, change, message: str) -> None:
    given = task(seed=find(6, nontrivial), teams=6)
    answer = gold_answer(given, tmp_path)
    target = answer["eliminated"][0]
    target["certificate"] = change(target)
    verdict = judge(given, answer, tmp_path)
    assert verdict["valid"] is False and message in verdict["details"]["per_team"][target["team"]]


def test_rejects_a_team_left_out_judged_twice_or_unknown(tmp_path: Path) -> None:
    given = task(seed=7, teams=6)
    answer = gold_answer(given, tmp_path)
    left_out = {**answer, "alive": answer["alive"][1:]} if answer["alive"] else {**answer, "eliminated": answer["eliminated"][1:]}
    assert "never judged" in judge(given, left_out, tmp_path)["message"]
    everyone = [e["team"] for e in answer["eliminated"]] + answer["alive"]
    twice = {**answer, "alive": answer["alive"] + [everyone[0]]}
    assert "more than once" in judge(given, twice, tmp_path)["message"]
    unknown = {**answer, "alive": answer["alive"] + ["Yankees"]}
    verdict = judge(given, unknown, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["unknown_teams"] == ["Yankees"]


def test_rejects_an_empty_answer(tmp_path: Path) -> None:
    given = task(seed=7, teams=6)
    verdict = judge(given, {"eliminated": [], "alive": []}, tmp_path)
    assert verdict["valid"] is False and verdict["score"] == 0.0


def test_a_team_that_can_only_tie_is_alive(tmp_path: Path) -> None:
    # Boundary: its best finish equals a rival's wins. Claiming that rival as a certificate must fail.
    def tie(given) -> bool:
        data = standings(given)
        alive = set(pin_eliminations(given, Path(".")).alive)
        n = len(data["names"])
        return any(
            data["names"][x] in alive and any(data["wins"][j] == best(data, x) for j in range(n) if j != x) for x in range(n)
        )

    given = task(seed=find(6, tie), teams=6)
    data = standings(given)
    answer = gold_answer(given, tmp_path)
    assert judge(given, answer, tmp_path)["valid"] is True
    n = len(data["names"])
    x = next(
        x for x in range(n)
        if data["names"][x] in answer["alive"] and any(data["wins"][j] == best(data, x) for j in range(n) if j != x)
    )
    rival = next(data["names"][j] for j in range(n) if j != x and data["wins"][j] == best(data, x))
    answer["alive"].remove(data["names"][x])
    answer["eliminated"].append({"team": data["names"][x], "certificate": [rival]})
    verdict = judge(given, answer, tmp_path)
    assert verdict["valid"] is False and "alive, but submitted as eliminated" in verdict["details"]["per_team"][data["names"][x]]


def test_divisions_with_no_elimination_and_with_only_trivial_ones_pass(tmp_path: Path) -> None:
    def none(given) -> bool:
        return not pin_eliminations(given, Path(".")).eliminated

    def trivial_only(given) -> bool:
        return bool(pin_eliminations(given, Path(".")).eliminated) and not nontrivial(given)

    for predicate in (none, trivial_only):
        given = task(seed=find(5, predicate), teams=5)
        output, reference = gold_run(given, tmp_path)
        assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is True


def test_rejects_a_tampered_answer_key(tmp_path: Path) -> None:
    given = task(seed=find(6, nontrivial), teams=6)
    output, reference = gold_run(given, tmp_path)
    reference.alive = reference.alive + [reference.eliminated[0].team]
    reference.eliminated = reference.eliminated[1:]
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is False
    assert verifier.verify_task(TASK, given, output, None, str(tmp_path))["valid"] is False


def test_input_checks_refuse_malformed_calls() -> None:
    assert verifier.verify_input("get_standings", task(seed=-1))["valid"] is False
    assert verifier.verify_input("get_standings", task(teams=3))["valid"] is False
    assert verifier.verify_input("get_standings", task(teams=9))["valid"] is False
    given = plain_output(task())
    names = standings(task())["names"]
    for team, subset in ((names[0], []), (names[0], [names[0]]), (names[0], [names[1], names[1]]), ("Yankees", [names[1]])):
        value = build_output({"task": given, "team": team, "subset": subset}, BoundInput)
        assert verifier.verify_input("subset_bound", value)["valid"] is False
    good = build_output({"task": given, "team": names[0], "subset": names[1:3]}, BoundInput)
    assert verifier.verify_input("subset_bound", good)["valid"] is True


def test_tool_outputs_are_checked(tmp_path: Path) -> None:
    given = task()
    made = as_sandbox(get_standings(given, tmp_path), StandingsOutput)
    assert verifier.verify_output("get_standings", given, made, str(tmp_path))["valid"] is True
    made.teams[0].wins += 1
    assert verifier.verify_output("get_standings", given, made, str(tmp_path))["valid"] is False
    names = standings(given)["names"]
    asked = build_output({"task": plain_output(given), "team": names[0], "subset": names[1:4]}, BoundInput)
    bound = subset_bound(asked, tmp_path)
    assert verifier.verify_output("subset_bound", asked, bound, str(tmp_path))["valid"] is True
    bound.beats = not bound.beats
    assert verifier.verify_output("subset_bound", asked, bound, str(tmp_path))["valid"] is False
