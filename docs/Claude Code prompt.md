# Claude Code prompt

These are the files and prompts that set Claude Code up to build the engine: a CLAUDE.md for the repo root, a kickoff prompt for M0 and M1, and one follow-up prompt per later milestone.

## How to use these

1. Export the Design doc and Build guide tabs as Markdown into `docs/design.md` and `docs/build-guide.md`.
2. Save the CLAUDE.md block below as `CLAUDE.md` in the repo root.
3. Start the game with `uvx balatrobot serve --fast`, then start Claude Code in the repo root and paste the kickoff prompt.
4. For each later milestone, start a fresh session and paste its follow-up prompt.
5. When an open question gets answered, update CLAUDE.md and `docs/design.md` before the next session.

## CLAUDE.md

```markdown
# MLBA Engine

An engine that plays Balatro under the Major League Balatro (MLBA) Season 4
multiplayer ruleset. Full spec: docs/design.md. Step-by-step plan:
docs/build-guide.md. Read both before starting any milestone.

## Hard rules

- Never copy Balatro's code or assets into this repo. The extracted Lua in
  ~/balatro-ref/ is a read-only reference for checking behavior. Never commit
  it, paste large parts of it, or publish it.
- The Multiplayer mod is GPL-3.0. Read it to learn behavior; ask me before
  copying any of its code.
- Check a seed tool's license before reusing its code. Ask me if unclear.
- The simulator must match the real game exactly. When unsure how the game
  behaves, check ~/balatro-ref/ or test it through BalatroBot. Never guess,
  and never simplify a rule.
- Tests before code. A feature is done only when its tests pass, including
  golden or differential tests against the real game where they apply.
- Ask before changing the ruleset, the PvP protocol, or the repo layout.

## Layout

- sim/            Rust crate: rng/, rules/, content/, mlba/, replay/
- sim-py/         PyO3 bindings (maturin)
- content/        our own data specs for jokers, consumables, vouchers, tags, decks, stakes
- harness/        BalatroBot client, trace recorder, differential tester
- solver/         in-round solver, PvP sub-game
- agent/          model and training
- eval/           baselines, rule tests, scenario diagnostics, ratings
- tests/fixtures/ recorded traces and golden hands

## Commands

- Rust tests: `cargo test` (in sim/)
- Python tests: `uv run pytest`
- Build bindings: `uv run maturin develop -m sim-py/Cargo.toml`
- Game with API: `uvx balatrobot serve --fast` (port 12346).
  Add `--headless` for batch runs and `--port N` for parallel instances.
- One API call: `uvx balatrobot api <method> '<json params>'`

## Determinism

- Simulator state is a pure function of (seed, deck, stake, actions). No
  wall clock, no unseeded randomness, no hash-map iteration order in game logic.
- Every state has a canonical hash. Compare states by content and order,
  never by card id.
- Lua numbers are doubles. Match floating-point behavior exactly.

## MLBA Season 4 ruleset (summary; details in docs/design.md)

- Both players play the same seed.
- Ante 1 is normal. From Ante 2, the Boss Blind is a PvP blind with no boss effect.
- 4 lives each. Lose 1 for any lost blind, PvP included. First to 0 loses.
- Comeback money: losing a life to a blind (PvP or normal) adds $4 x all
  lives lost so far to that round's payout. Timer deaths pay nothing but
  count toward the total (timer to 3 lives, then PvP to 2: payout gets $8).
- PvP blinds pay no $1 per remaining hand; normal blinds still do.
- Timer (not simulated; handled by the live bridge): off by default. By
  convention, whoever reaches the PvP blind first starts it on the opponent.
  Length is 180 s + 60 s per blind the starter skipped that ante; the
  opponent sees it only from 180 s down. Hitting 0 costs the timed player a
  life. It stops when they enter the PvP blind.
- Vanilla content, no multiplayer jokers or decks. The Order is disabled:
  vanilla per-ante shop queue, rerolls consume it, pack contents fixed per seed.
- Voucher and Bloodstone sync per the mod; verify against its code.

## PvP protocol

1. Hand 1 is simultaneous: commit, then reveal.
2. After hand 1, the lower score plays next, regardless of hands left.
3. The leader may wait or play.
4. Tied scores: both act independently again.
5. If the player who must play has no hands left, the blind ends and the
   leader wins without playing their remaining hands.
6. Both out of hands: higher score wins. Exact tie is an open question;
   raise it, don't invent an answer.

## Objective

The in-round solver maximizes the expected value of the end-of-blind state
(lives, money with interest steps, consumables, hand levels, joker counters,
deck changes, hands left), not the score. See docs/design.md, "Objective".

Never hard-code strategy, such as when to play for value, when to concede a
PvP, which hands to keep, or when to skip a blind. The value function learns it. Pass/fail tests
check only rules, legality, and etiquette; strategic choices go in scenario
diagnostics for review.

## Workflow

- One milestone per session. Read the docs, propose a plan, and wait for my OK.
- Keep docs/progress.md current: what's done, what's tested, open questions.
- When the docs don't cover a behavior, write it in docs/progress.md and ask.
- Commit after each batch of passing tests, with a clear message.
```

## Kickoff prompt (M0 and M1)

```text
Read CLAUDE.md, docs/design.md, and docs/build-guide.md. We're starting the
MLBA engine with milestones M0 (setup and trace recorder) and M1 (scoring
engine).

The game is running locally with BalatroBot on port 12346. The game's Lua is
in ~/balatro-ref/ (read-only).

Before writing any code, give me a plan that covers:
- the repo scaffold and CI
- the typed BalatroBot client and the trace recorder (M0)
- the scoring engine's data model in Rust: cards, enhancements, editions,
  seals, jokers, and how content specs and effect hooks fit together
- how you'll confirm the scoring order against evaluate_play in ~/balatro-ref/
- the golden-test pipeline: building scenarios with start/add/set/play,
  reading round.chips, and storing fixtures
- which jokers you'll cover first, and how you'll track coverage
Then wait for my OK.

After I approve, build M0 and stop. Show me one full seeded run recorded as a
trace and the check that replays it through the game with every state
matching. Wait for my OK again, then build M1.

M1 is done when 1,000+ recorded hands match the real game with zero
mismatches and every deterministic scoring joker has at least one golden
test. Probabilistic effects (Lucky cards, Bloodstone, Misprint, 8 Ball) wait
for M2. Finish by showing me the coverage table and anything you added to
docs/progress.md.
```

## Follow-up prompts

Each starts a fresh session for one milestone.

### M2 — RNG and generation

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M2 (RNG and generation).

Plan first, then wait for my OK. Cover: how Balatro's seeded streams work
(from ~/balatro-ref/), which stream keys and call order you'll reproduce,
floating-point matching, and how you'll validate shops, packs, tags, bosses,
and vouchers against the real game on 1,000 seeds. Check the licenses of
Immolate and Motely before reusing anything from them.

Done when generation matches the real game for Antes 1-8 on 1,000 seeds and
M1's probabilistic golden tests pass.
```

### M3 — Full simulator

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M3 (full single-player simulator).

Plan first, then wait for my OK. Cover: the state machine, the full action
set and legal-move generator, the canonical state hash, the replay format,
the differential tester running several headless game instances, and Python
bindings with batched stepping.

Done when 200 real-game traces replay with zero state differences and a
scripted policy runs 100+ full games per second per core. Report the
benchmark numbers.
```

### M4 — In-round solver

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M4 (in-round solver).

Plan first, then wait for my OK. Cover: candidate generation, sampled-draw
simulation that records the full resource outcome of each line, pruning of
dominated lines, ranking with shadow prices kept in a config file, the
greedy max-score baseline, and the scenario diagnostics listed in docs/design.md.

Done when, over 10,000 sampled rounds, the solver ends with more money at
cash-out than greedy max-score with no rise in blind failures, and the scenario
diagnostics are ready for my review.
```

### M5 — MLBA layer

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M5 (MLBA layer).

First, clone the Balatro Multiplayer mod and read its Major League ruleset
and PvP code. Don't copy any of it (GPL-3.0). Answer the open questions in
docs/design.md from what you find, report back, and wait for my OK.

Then build: the ruleset config, a two-player environment where the PvP
protocol decides whose turn it is, and unit tests for every protocol case,
including ties and the early win. Add the timer convention to the live
bridge (see "Timer protocol" in docs/design.md).

Done when the protocol tests pass and 10,000 same-seed scripted games finish
with no illegal state.
```

### M6 — Agent v1

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M6 (agent v1).

Plan first, then wait for my OK. Cover: the model from docs/design.md (entity
transformer, five heads), observation encoding, masked action heads, the PPO
setup, the stake curriculum, the self-play league, and a compute estimate.
Prove the loop end to end on CPU with a tiny model before scaling up.

Done when the agent wins 70%+ of same-seed games against the scripted bot.
```

### M7 — Analysis mode

```text
Read CLAUDE.md, docs/design.md, docs/build-guide.md, and docs/progress.md.
Start M7 (analysis mode).

Plan first, then wait for my OK. Cover: known-seed beam search with the value
network as the heuristic and the opponent's recorded PvP scores held fixed,
and a win-probability estimate from broadcast-visible state.

Done when it produces a best line for recorded games where the seed is known.
```
