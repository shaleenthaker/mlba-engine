# Build guide

This guide takes the design from an empty folder to a trained agent, one milestone at a time. Each milestone ends with a test that has to pass before the next starts.

## Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| Balatro (Steam, Windows or macOS) | 1.0.1+ | The real game, for validation |
| [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) | 0.9+ (Multiplayer mod needs 0.9; BalatroBot needs 0.8) | Loading mods |
| [Steamodded](https://github.com/Steamodded/smods) | The version the Multiplayer mod's README names, which also satisfies BalatroBot | Mod loader |
| [uv](https://docs.astral.sh/uv) | 0.9.21+ | Python environments; runs BalatroBot's CLI |
| Python | 3.11+ | Harness, solver, training |
| Rust (stable) + maturin | Current | Simulator core and its Python bindings |
| Git, Claude Code | Current | Version control, the coding agent |
| NVIDIA GPU | Optional until M6 | League training |

Version floors come from the [BalatroBot install guide](https://coder.github.io/balatrobot/latest/installation/) and the [Multiplayer mod README](https://github.com/Balatro-Multiplayer/BalatroMultiplayer).

## Set up modded Balatro for validation

The real game, driven through BalatroBot's JSON-RPC API, is the ground truth every simulator test is checked against.

1. **Install Lovely Injector.** Put `version.dll` (Windows) or `liblovely.dylib` (macOS) in the Balatro game directory.
2. **Install Steamodded** into `Mods/smods/`.
3. **Install BalatroBot** from its [releases page](https://github.com/coder/balatrobot/releases) into `Mods/balatrobot/`. Add DebugPlus only if you want its debug mode.
4. **Launch the game through the CLI** (on macOS this is required, because Steam can't launch the modded game directly):

   ```bash
   uvx balatrobot serve --fast
   ```
5. **Check the connection.** This should return `{"status":"ok"}`:

   ```bash
   curl -X POST http://127.0.0.1:12346 -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "health", "id": 1}'
   ```
6. **Start a seeded run and read its state:**

   ```bash
   uvx balatrobot api start '{"deck": "RED", "stake": "WHITE", "seed": "TEST123"}'
   uvx balatrobot api gamestate
   ```
7. **Extract the game's Lua as a read-only reference.** The game file is a zip archive: `Balatro.exe` on Windows, `Balatro.app/Contents/Resources/Balatro.love` on macOS. Unzip a copy into a folder outside the repo, such as `~/balatro-ref/`. Use it to check behavior; never copy it into the repo or publish it.

| Platform | Mods directory |
| --- | --- |
| Windows | `%AppData%/Balatro/Mods/` |
| macOS | `~/Library/Application Support/Balatro/Mods/` |
| Linux (Proton) | `~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/` |

Useful `serve` flags for automated testing: `--headless --fast` for speed, `--port` to run several game instances in parallel. Logs go to `logs/{timestamp}/{port}.log` ([CLI reference](https://coder.github.io/balatrobot/latest/cli/)).

The API covers everything the harness needs: `start` (with seed), `gamestate`, `select`, `skip`, `play`, `discard`, `rearrange`, `buy`, `pack`, `sell`, `reroll`, `use`, `cash_out`, `next_round`, plus debug methods `add` and `set` for building test scenarios ([API reference](https://coder.github.io/balatrobot/latest/api/)).

Install the Multiplayer mod only when you reach M5. Keep BalatroBot disabled whenever you play multiplayer normally, and never queue ranked with it loaded.

## Repo layout and toolchain

One repo, with the Rust simulator as a library that Python calls through PyO3 bindings.

```text
mlba-engine/
  CLAUDE.md            instructions for Claude Code (from the third tab)
  docs/
    design.md          the Design doc tab, exported as Markdown
    build-guide.md     this tab, exported as Markdown
  sim/                 Rust crate: rng/, rules/, content/, mlba/, replay/
  sim-py/              PyO3 bindings, built with maturin
  content/             joker, consumable, voucher, tag, deck, stake specs (our own data files)
  harness/             BalatroBot client, trace recorder, differential tester
  solver/              in-round solver, PvP sub-game
  agent/               model, training loops
  eval/                baselines, rule tests, scenario diagnostics, ratings
  tests/fixtures/      recorded traces and golden hands
```

First-time setup:

```bash
mkdir mlba-engine && cd mlba-engine && git init
uv init --bare                       # pyproject.toml only
uv add httpx pydantic numpy
uv add --dev pytest hypothesis maturin
cargo new --lib sim
```

Add PyTorch only at M6. Add `~/balatro-ref/`, game saves, and large trace files to `.gitignore` from the first commit.

## Build steps by milestone

### M0 — Setup and trace recorder

1. Scaffold the repo as above, with CI running `cargo test` and `pytest`.
2. Write a typed Python client for BalatroBot: one method per API call, Pydantic models for the game state.
3. Write the trace recorder: for every action, append `{action, state_before, state_after}` to a JSONL file, with seed, deck, and stake in a header line.
4. Record one full seeded run with a simple scripted policy.

**Done when:** a complete run replays from its trace file through the real game and every recorded state matches.

### M1 — Scoring engine

1. Implement poker-hand detection for all 12 hands, plus the jokers that change hand detection or which cards score (Four Fingers, Shortcut, Smeared Joker, Splash).
2. Implement the scoring pipeline: base chips and mult from hand level, each scoring card left to right (rank chips, enhancement, edition, seals and retriggers, on-score joker effects), held-in-hand effects, then jokers left to right with their editions. Confirm the exact order against `evaluate_play` in the reference Lua rather than from memory.
3. Build golden tests with BalatroBot: `start` a seeded run, `add` jokers and cards with editions and seals, `set` hands and money, `play`, then read `round.chips`. Save each case as a fixture.
4. Cover deterministic effects first. Probabilistic ones (Lucky cards, Bloodstone, Misprint, 8 Ball) wait for M2's RNG.
5. Generate a coverage report: for each joker, whether it is implemented and golden-tested.

**Done when:** 1,000+ recorded hands match the real game with zero mismatches, and every deterministic scoring joker has at least one golden test.

### M2 — RNG and generation

1. Reimplement Balatro's seeded random streams in Rust. Lua numbers are doubles, so match floating-point behavior exactly.
2. Read existing seed tools (Immolate, Motely, The Soul) to understand stream keys and ordering. Check each tool's license before reusing any of its code.
3. Generate shops (the per-ante queue), packs, tags, bosses, and vouchers from a seed.
4. Validate against the real game: `start` each seed through BalatroBot, walk the run with a scripted policy, and compare every shop, pack, tag, and boss.

**Done when:** generation matches the real game for Antes 1–8 on 1,000 seeds, and the probabilistic scoring effects from M1 now pass their golden tests.

### M3 — Full single-player simulator

1. Mirror BalatroBot's state machine: blind select, selecting hand, round evaluation, shop, pack opened, game over.
2. Implement every action with a legal-move generator that also produces the action mask.
3. Add a canonical state hash and replay files (seed, deck, stake, action list).
4. Build the differential tester: run the same policy in both the real game and the simulator, and compare canonical state after every action. Run several headless game instances on different ports in parallel.
5. Expose the simulator to Python through maturin, with batched stepping.

**Done when:** 200 real-game traces replay with zero state differences, and a scripted policy runs 100+ full games per second per core.

### M4 — In-round solver

1. Generate candidates: every 1–5 card subset of the hand, as a play or a discard (436 for an 8-card hand).
2. For each, simulate against sampled draws from the known remaining deck and record the full outcome: score, money, consumables created, level changes, joker counters, hands and discards left.
3. Drop lines beaten on every dimension, rank the rest with a hand-tuned shadow-price table in a config file, and pick the best.
4. Write the baselines (greedy max-score) and the scenario diagnostics from the design doc. Strategic choices are reported for review, never written as pass/fail tests.

**Done when:** over 10,000 sampled rounds, the solver ends with more money at cash-out than greedy max-score with no rise in blind failures, and the scenario diagnostics have been reviewed.

### M5 — MLBA layer

1. Clone the Multiplayer mod and read the Major League ruleset and PvP code to settle the design doc's open questions. The mod is GPL-3.0: reading it is fine, but copying its code into this repo would put the repo under the GPL.
2. Add a ruleset config: 4 lives, PvP from Ante 2, comeback money ($4 × all lives lost so far, paid only on blind losses; timer deaths count toward the total but pay nothing), no $1 per remaining hand in PvP, strict turn order, voucher and Bloodstone sync.
3. Build the two-player environment, where the protocol decides whose turn it is.
4. Write protocol unit tests for every case in the design doc, including ties and the early win. Add the timer convention to the live bridge: start the timer when first to the PvP blind, and when timed, fit the rest of the ante inside the countdown.
5. Stretch: validate against real multiplayer games using a self-hosted Multiplayer server and two local game instances.

**Done when:** protocol tests pass and two scripted agents complete 10,000 same-seed MLBA games without an illegal state.

### M6 — Agent v1

1. Implement the model from the design doc in PyTorch, with all five heads.
2. Train single-player with PPO and action masking, following the stake curriculum.
3. Start the self-play league: current agent, frozen snapshots, exploiters, ghost opponents.
4. Move to GPUs once single-player training is stable.

**Done when:** the agent wins 70%+ of same-seed games against the scripted bot.

### M7 — Analysis mode

1. Add known-seed beam search with the value network as the heuristic and the opponent's recorded PvP scores fixed.
2. Add a win-probability estimate from broadcast-visible state for both players.

**Done when:** it produces a best line for recorded games where the seed is known.

## Testing and validation

The simulator is only useful if it matches the real game exactly, so tests are layered from single effects up to whole runs.

| Layer | What it checks | Needs the real game? |
| --- | --- | --- |
| Unit tests | One content item or rule in isolation | No |
| Golden hands | Score of a recorded hand matches the game | Recorded once, then fixtures |
| Generation | Shops, packs, tags, bosses per seed | Recorded once, then fixtures |
| Differential traces | Full state after every action of a run | Recorded once, then fixtures |
| Property tests | Same seed and actions give the same state hash; replays round-trip; illegal actions are rejected | No |
| Protocol tests | Every PvP turn-order case, including ties and the early win | No |
| Scenario diagnostics | Solver and agent decisions in hand-built scenarios, reported for review rather than pass/fail | No |

Practices that keep this manageable:

- **Compare canonical state.** Card ids in the game aren't stable, so compare by content and order, not by id.
- **Diff after every action.** An RNG desync shows up far from its cause if you only check end states.
- **CI runs on fixtures.** Recorded traces live in `tests/fixtures/`, so CI never needs the game. Re-record only when the game or a mod updates.
- **Coverage report.** For each joker, consumable, voucher, tag, and boss: implemented, golden-tested, diff-tested. Untested content stays out of training.

## Working with Claude Code

Claude Code does the building; your job is to set it up with the right context and review each milestone before the next.

1. Export the Design doc and Build guide tabs as Markdown into `docs/design.md` and `docs/build-guide.md`.
2. Copy the CLAUDE.md from the third tab into the repo root. Claude Code reads it at the start of every session.
3. Start Claude Code in the repo and paste the kickoff prompt. It covers M0 and M1.
4. For each later milestone, start a fresh session and paste that milestone's follow-up prompt.
5. Ask for a plan before code on every milestone, and review it. Most mistakes are cheaper to catch in the plan.
6. Keep the game running (`uvx balatrobot serve --fast`) while Claude Code records golden tests and traces; it calls the local API itself.
7. Commit after each batch of passing tests, so a bad change is one `git revert` away.

Update CLAUDE.md whenever a rule changes or an open question gets answered, so every later session starts from the current spec.

## Rules of the road and troubleshooting

**Rules**

- Game code and assets never enter the repo. The extracted Lua lives in `~/balatro-ref/` and is read-only.
- The engine and BalatroBot are never used in ranked, MLBA, or any match without the opponent's agreement. Ranked rules ban debug mode and unapproved mods ([rules](https://balatromp.com/docs/ranked-matchmaking/Ranked-rules)).
- The Multiplayer mod is GPL-3.0. Reading it is fine; copying its code puts this repo under the GPL, so decide that deliberately.
- Check a seed tool's license before reusing its code.

**Troubleshooting** (from the [BalatroBot CLI reference](https://coder.github.io/balatrobot/latest/cli/))

| Symptom | Fix |
| --- | --- |
| Connection refused | Check the game is running and read `logs/{timestamp}/{port}.log` |
| Mod not loading | Reinstall Lovely and Steamodded; check versions against both mods' minimums |
| Port in use | `uvx balatrobot serve --port <other port>` |
| Game crashes | Add `--no-shaders`, or run `--headless` |
| Can't launch through Steam on macOS | Always launch with `uvx balatrobot serve`, which runs the game directly |
