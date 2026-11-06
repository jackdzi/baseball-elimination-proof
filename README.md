# Baseball Elimination Proof

A `nanoagent.plugin/v0001` plugin. Its task, `find-eliminated`, gives an agent
a late-season baseball division (4 to 8 teams: wins, losses, and the games
each team has left inside and outside the division) and asks which teams are
mathematically eliminated from first place. Every elimination must come with
a certificate: a group of rivals who, between their wins and the games they
still play each other, must leave one of them ahead of the team. The division
comes from a seed, so every task can be rebuilt exactly, and a deterministic
verifier decides every team with its own maximum flow and checks every
certificate with exact fractions.

## Tools

| Tool | Does | Code |
|---|---|---|
| `get_standings` | The division: each team's wins, losses, games left in and outside the division and best possible wins, and the games left between each pair of teams | `src/plugin/division.py` |
| `subset_bound` | For a team and a group R of rivals: the team's best possible wins, R's wins, the games among R, the bound (wins + games among) / \|R\| as a reduced fraction, and whether it is greater than the team's best. It states facts and never says whether a team is eliminated | `src/plugin/division.py` |
| `pin_eliminations` | The answer key: the standings' sha256 and every eliminated team with the certificate a minimum cut gives | `src/plugin/division.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `find-eliminated` | Judges every team eliminated or alive, with a certificate for each elimination, and submits them | `agent`, with `get_standings` and `subset_bound`; reference `pin_eliminations` |

## The task

Input: `seed` (0 to 1,000,000,000) and `teams` (4 to 8). The agent calls
`get_standings`, tests groups of rivals with `subset_bound` (several calls per
step), and submits `eliminated` (each team with its certificate) and `alive`.

The rule: team x's best finish is its wins plus every game it has left. x is
eliminated exactly when some group R of other teams has
(wins of R + games among R) / |R| > x's best finish. A team that can at best
tie for first is alive. By max-flow/min-cut, a group like this exists exactly
when the remaining division games cannot be split so that no rival passes x.

## Ground truth and verification

Divisions are drawn by a sha256-based generator (`src/plugin/rng.py`), never
`random`. Two seeds in ten are tight races (often no elimination), five have a
block of contenders with many games left among themselves (eliminations that
need a group of rivals to prove), and three are spread wide (eliminations a
single rival proves).

`verify_task` (in `verifier/division.py`):

1. Rebuilds the division from the seed with its own copy of the generator,
   and checks the pinned answer key: its sha256, its eliminated and alive
   teams, and that every pinned certificate holds.
2. Decides every team itself with a depth-first augmenting-path maximum flow
   on an index matrix (the tools use a breadth-first one on named nodes).
3. Checks that every team is judged exactly once and names no unknown team.
4. For every team submitted as eliminated, checks the certificate: known
   teams, not empty, no team twice, not the team itself, and the bound
   strictly greater than the team's best finish, with `Fraction`. Any valid
   certificate passes, not only the key's.

The verdict is valid only when every team is judged right with a valid
certificate; its score is the share of teams judged right. `verify_input`
refuses a seed or team count out of range and a `subset_bound` call with an
unknown team, an empty group, a team twice or the tested team in its group.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no network), tools, task
├── contract.py      # each tool's and task's typed input and output
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable names needed (none)
├── src/plugin/      # the MCP server (__main__.py), the generator (rng.py) and the tools (division.py)
├── tests/           # the verifier's tests, tool tests with two textbook divisions, a 2,000-division
│                    #   agreement test against brute force, an MCP smoke test, and a scripted
│                    #   no-model agent (scripted_agent.py)
├── ui/              # renderers.js and renderers.css: outputs drawn from their JSON Schema
├── product/         # the product page: product.yaml and icon.svg
└── verifier/        # the deterministic verifier: division.py, its generator copy rng.py, checks.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

No network and no data files: every division comes from its seed. NanoAgent
passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
