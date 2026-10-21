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