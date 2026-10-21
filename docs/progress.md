# Progress

## Decisions (2026-10-21)

- **Ground truth is the Steamodded-patched game**, not vanilla `evaluate_play`.
  BalatroBot and the Multiplayer mod both run on Steamodded, which replaces the
  scoring pipeline with `SMODS.calculate_*`. Targets: Balatro 1.0.1o,
  Steamodded 26.1002.0, BalatroBot 1.5.2. Steamodded is GPL-3.0: read it, never copy it.
- **Joker counters come from an instrumentation mod** (our own code) that exposes
  raw `card.ability` values, rather than parsing UI text. Built in M1.
- **M1 golden tests run in Small and Big Blinds.** Boss scoring effects come with
  blind logic in M3; MLBA games see only one boss (Ante 1).
- Rust pinned to 1.99.1 (`rust-toolchain.toml`). Repo is its own git repo with
  remote `origin` = github.com/shaleenthaker/mlba-engine.

## M0: setup and trace recorder

### Done and tested

- Cargo workspace (`sim`, `sim-py`), uv project, PyO3 bindings building with
  maturin (`mlba_sim.game_version()`).
- CI workflow (`.github/workflows/ci.yml`): fmt, clippy, cargo test, pytest on
  fixtures only. Not yet run on GitHub (nothing pushed).
- `harness/client.py`: one typed method per BalatroBot endpoint, typed errors.
- `harness/models.py`: Pydantic models, extra fields forbidden, validated
  against real responses from every game state (`tests/fixtures/api/`).
- `harness/canonical.py`: canonical state (card ids dropped, order kept),
  sha256 state hash, path-level diff.
- `harness/trace.py`: JSONL traces (header line, then one line per action with
  `state_before` and `state_after`); `.gz` supported.
- `harness/policy.py`: deterministic scripted policy for recording only.
- `harness/recorder.py`, `harness/replay.py`, CLI `python -m harness record|replay`.
- 59 Python tests pass; 1 Rust test passes.
- **Exit criterion met.** `tests/fixtures/traces/MLBA0001-RED-WHITE.jsonl.gz`
  is a full seeded run (Red Deck, White Stake, 16 actions: start, select,
  discard, play, cash_out, buy, next_round, ending in GAME_OVER at Ante 1
  round 2). `python -m harness replay` on it through the real game: 16 steps,
  31 states compared, 0 mismatches. A copy with one changed action fails at
  that step with the differing fields listed. CI checks the committed trace's
  integrity offline (`tests/harness/test_recorded_traces.py`).

### Required game setup

- Steamodded's **vanilla run select** must be on (`["vanilla_run_select"] = true`
  in `config/Steamodded.jkr`, or the toggle in Steamodded's settings).
  Without it, BalatroBot 1.5.2's `start` fails with
  `start.lua:116: attempt to index field 'viewed_back' (a nil value)`:
  Steamodded 26.1002.0's own run-select UI (`G.UIDEF.run_select_galdur`)
  never sets `G.GAME.viewed_back`, which BalatroBot's `start` assumes.
- The harness also retries `start` if it hits this error right after `menu`.

## Observations about the API

- Card ids are the game's `sort_id`; they keep counting across runs, so the
  same seed gives different ids. Canonical state drops them.
- Lua's JSON encoder writes empty tables as `[]`; models accept `[]` for objects.
- Numbers are encoded with `%.14g`: exact for integers up to about 1e14; above
  that, compare at 14 significant digits.
- `modifier.enhancement` on jokers and consumables is the card's `ability.effect`
  (for example `MULT` on Joker), not an enhancement.
- The menu state keeps stale data from the previous run, so a trace's `start`
  step has `state_before = null`.
- The BalatroBot 1.5.2 release still says 1.5.1 in `balatrobot.json`; versions
  are read from its `pyproject.toml`.

## Open questions

- Traces and fixtures include the game's card description text (`value.effect`).
  BalatroBot's own public docs carry the same strings. Keep them in committed
  fixtures, or strip `effect` before committing once the instrumentation mod
  gives raw values?
