# MLBA Engine — Design Doc

Oct 18, 2026 · @Shaleen

## Overview

The goal is an engine that plays Balatro at a strong level under the Major League Balatro (MLBA) Season 4 ruleset. It is built from three parts: a fast, validated simulator; a neural network that estimates win probability and proposes actions; and search that combines the two at decision time.

The engine runs in two modes:

- **Play mode.** It sees only what a player sees on screen: its own run, the opponent's lives, and the opponent's live PvP score. This is the mode for self-play training and sparring.
- **Analysis mode.** Given a finished game's seed and both players' PvP scores, it searches for the best line in hindsight. This is the mode for VOD review and a broadcast win-probability bar.

**Goals**

1. A simulator of vanilla Balatro plus the MLBA layer that matches the real game step for step.
2. An in-round solver that maximizes the value of the state you leave a blind in, not the score.
3. A self-play-trained agent that beats its earlier versions and scripted baselines in same-seed matches.

**Non-goals**

- Playing in ranked queues, MLBA, or any match where the opponent hasn't agreed to face a bot.
- Redistributing Balatro's code or assets. The game's Lua is a local reference for checking behavior, never committed or published.
- Other rulesets for now. Ruleset rules live in one configurable layer so Ranked, Minor League, and others can be added later.

**Design principle: no hand-written strategy.** This doc describes tradeoffs, never rules for resolving them. Skipping a blind, playing for value, going all in on score, conceding a PvP: each is a choice the model makes from the state it's in, judged by its effect on P(win). Where the doc names a consideration, it is an input for the model to weigh, not a policy.

## Ruleset spec (MLBA Season 4)

The simulator enforces vanilla Balatro with a PvP blind in place of every Boss Blind after Ante 1, four lives per player, and the vanilla shop queue. Rows marked "verify" need checking against the mod's code before the MLBA layer is final.

| Rule | Simulator behavior | Source |
| --- | --- | --- |
| Seed | Both players play the same seed | [MLBA](https://majorleaguebalatro.com/about) |
| Ante 1 | Normal Small, Big, and Boss Blinds | [MLBA](https://majorleaguebalatro.com/about) |
| Ante 2 onward | Boss Blind replaced by a PvP blind with no boss effect | [MLBA](https://majorleaguebalatro.com/about) |
| Lives | 4 each; lose 1 for any lost blind, PvP included; first to 0 loses the game | [MLBA](https://majorleaguebalatro.com/about) |
| Comeback money | Losing a life to a blind (PvP or normal) adds $4 × all lives lost so far to that round's payout. Timer deaths pay nothing themselves but count toward the total: drop to 3 lives on the timer, then to 2 in a PvP, and that payout gets $8 | Confirmed in design discussion |
| Timer | Off by default; whoever reaches the PvP blind first starts it on the opponent; 180 s + 60 s per skip; hitting 0 costs a life (see Timer protocol) | [MLBA](https://majorleaguebalatro.com/about); start convention, skip extension, and display confirmed in design discussion |
| Stacked losses | A timer loss and a blind loss can both happen in the same round | [Mod releases](https://github.com/Balatro-Multiplayer/BalatroMultiplayer/releases) |
| Content | Vanilla jokers, decks, and stakes; no multiplayer jokers or decks | [Mod docs](https://balatromp.com/docs/rulesets/Major-and-Minor-league) |
| Shop queue | The Order off: each ante has one ordered queue, rerolls consume it, pack contents fixed per seed | [Mod docs](https://balatromp.com/docs/rulesets/Major-and-Minor-league), [Balatro HQ](https://balatrohq.com/tools/shop-replay/) |
| Vouchers | Synced: both players see the same voucher, or its Level 2 version if they hold the base | [MLBA](https://majorleaguebalatro.com/about) (verify exact logic) |
| Bloodstone | Hits synced between players in PvP | [MLBA](https://majorleaguebalatro.com/about) (verify) |
| Idol | Mod fix makes one-sided Idol hits less likely | [MLBA](https://majorleaguebalatro.com/about) (verify) |
| Visibility | Opponent's lives and live PvP score visible; their build, deck, and location hidden | [MLBA](https://majorleaguebalatro.com/about), [Set Side B](https://setsideb.com/?p=10430) |
| Early win | If the opponent runs out of hands while behind, you win without playing your remaining hands | [Set Side B](https://setsideb.com/?p=10430) |
| Rewards on PvP loss | Money and rewards paid as if you'd won | [Set Side B, Season 3](https://setsideb.com/tag/balatromultiplayer/) (verify for Season 4) |
| Hands left in PvP | No $1 per remaining hand at a PvP blind's payout; normal blinds still pay it | Confirmed in design discussion |

**Match format** (used later by a deck/stake pick advisor, not by the simulator):

- Regular season: 3 games per match, 1 point per game won plus 1 for the match.
- Game 1's deck and stake come from a wheel spin. The loser of each game picks the deck or the stake for the next, or defers.
- Playoffs: best of 5; the higher seed picks for games 1, 3, and 5. A deck or stake can't be reused once played.

## PvP blind protocol

After hand 1, whoever is behind must play next, however many hands either player has left; the leader may wait. The mod doesn't enforce this, so it is a player convention. The simulator enforces it for self-play, and the bot follows it against humans.

**Rules the simulator enforces**

1. Hand 1 is simultaneous. Each player commits a first hand without seeing the other's hand-1 score. Discards before it are free.
2. After hand 1, the player with the lower score plays next, regardless of hands remaining on either side.
3. The leader may wait, or play anyway.
4. If scores are tied, both players act independently again, as in hand 1.
5. If the player who must play has no hands left, the blind ends and the leader wins without playing their remaining hands.
6. If both players run out of hands, the higher score wins. An exact final tie is an open question.

Implement hand 1 as a commit-then-reveal step. Put the protocol behind a ruleset setting (`turn_order: strict | free`) so other rulesets can change it.

**Bot etiquette against humans**

- Hand 1: decide with the opponent's hand-1 score masked, even if the human has already played, and commit as soon as the decision is made.
- After hand 1: play promptly when behind; wait when ahead.
- With no PvP timer, a human who is behind can stall. The bot keeps waiting, with a configurable patience setting after which it may play anyway.

**What follows for the solver**

- After hand 1, a PvP blind is a sequential game over five numbers: both scores, both hand counts, and who must play. It is small enough to solve by working backward from the end.
- Extra hands are worth win probability when trailing (more attempts to overtake) but are only insurance when leading, since unplayed hands pay nothing at the end of a PvP blind. Whether the leader plays a hand at all, and whether it is a scoring or a value hand, depends on the life at stake, P(win), and the score the opponent may still put up. There is no fixed rule; the value function learns it.
- A trailer with little chance of catching up will often do better playing for value; when to switch is learned the same way.
- Hand 1 is the only blind bid for turn order, and the lead it buys can be lost. A strong opener is worth more in close races than the "save the big hand for last" habit suggests.

## Timer protocol

The timer is off by default. By MLBA convention, whoever reaches the PvP blind first must switch it on, and it then runs against the opponent until they enter the PvP blind. Like turn order, starting it is an agreement between players, not something the mod forces.

1. **Start.** A player who reaches the PvP blind before the opponent starts the timer.
2. **Length.** 180 s, plus 60 s for each blind the starting player skipped that ante: 240 s after one skip, 300 s after skipping both Small and Big.
3. **Display.** The timed player sees the countdown only from 180 s down, so they can't tell whether the starter skipped. From their side it is always a 180 s countdown that appears at some point.
4. **Expiry.** If it reaches 0 before the timed player enters the PvP blind, they lose a life. This can stack with losing a blind in the same round.
5. **Stop.** It stops when the timed player enters the PvP blind; there is no timer inside a PvP blind.

**Simulator.** Self-play has no wall clock, so the timer isn't simulated. The extra 60 s per skip offsets the head start a skip gives, so the engine shouldn't value skips for timer pressure.

**Live play.**

- When the bot reaches the PvP blind first, it starts the timer right away.
- When the countdown appears on its side, the bot treats it as the budget for the rest of the ante: it shrinks its search time to fit and enters the PvP blind with a safety margin.
- The countdown appearing tells the bot the opponent has reached the PvP blind, but not when or whether they skipped. The opponent model can use it only as a weak signal.

## Objective: value of the end-of-blind state

The in-round solver maximizes the expected value of the state you leave a blind in, where V is the network's estimate of P(win game). Score matters only as the way to keep lives; money, consumables, levels, and joker state count just as directly.

```latex
a^* = \arg\max_a \; \mathbb{E}\left[ V(s_{\text{end}}) \mid a \right]
```

The end state includes both players' lives, money, consumables, hand levels, joker counters, deck changes, and hands left unplayed.

### Value triggers

Value sources fire at different moments, and the timing is what creates conflicts the solver has to resolve.

| When it pays | Examples | What it pulls toward |
| --- | --- | --- |
| Card is played and scores | Gold seals, Golden Ticket, Rough Gem, Business Card, To Do List, Space Joker, 8 Ball | Playing "value hands" that may score poorly |
| Card is held at round end | Gold cards, Blue seals | Digging these up and keeping them in hand, so the final hand matters |
| Card is discarded | Purple seals, Faceless Joker, Mail-In Rebate, Trading Card, Burnt Joker | Spending discards on payouts instead of digging |
| Resource left unused | $1 per remaining hand (normal blinds only), Delayed Gratification | Ending fast and not discarding |
| Joker state changes | Green Joker, Ride the Bus, Ice Cream, Seltzer, Ramen, scaling jokers | Every extra hand or discard has a cost or benefit beyond score |

### Normal blinds

The accepted strategy is to leave the blind with as much value as possible without losing a life. That is a chance-constrained problem: maximize expected value gained while keeping P(clear) above a threshold. The threshold depends on lives and ante. With four lives on Ante 2, a 2% risk to dig for a Gold seal can be right; with one life it almost never is. Folding the life loss into V handles this without a hand-set threshold.

Money is nonlinear. Interest steps at multiples of $5 up to the cap, so finishing at $25 instead of $24 is worth more than $1. The solver works on money totals, not summed payouts.

### Skipping blinds

Skipping a Small or Big Blind gives up that blind and the shop after it in exchange for the blind's tag, plus whatever the skip protects. Skips serve several purposes:

- **The tag.** Mostly an early-game factor. In Ante 1, Investment and Rare tags are common reasons to skip, and depending on deck and stake, other tags can be worth it too. Which skips pay off, and when, is for the model to find out.
- **Keeping a good roll.** Jokers whose target changes each round, such as The Idol and Ancient Joker, keep their current target through a skip. When the roll lands on the card or suit that's strongest for you, skipping holds it. This matters most when the deck isn't committed to one suit or card, so a good roll is less likely to come back.
- **Preserving jokers.** A skip uses no hands or rounds, so it protects jokers that run down, such as Seltzer and, on higher stakes, Perishable jokers.
- **Protecting Glass cards.** Occasionally the only reasonable way through a blind risks your Glass cards. If losing them would hurt your chances in the next PvP more than the skip costs, skipping keeps them for the PvP.

The costs are the blind's payout, any value you would have gained playing it, and, most importantly, everything in the shop you don't visit. A skip also lengthens the timer you start on your opponent (see Timer protocol). How a skipped shop interacts with the per-ante queue and pack generation is a simulator detail to verify in M2.

There is no rule for when to skip. The model weighs each skip against playing the blind by its effect on P(win), like every other decision here.

### PvP blinds: value versus win

Each candidate line has two outcomes:

```latex
U(a) = P(\text{win} \mid a)\, V(s^{\text{win}}_{\text{end}}) + \big(1 - P(\text{win} \mid a)\big)\, V(s^{\text{loss}}_{\text{end}})
```

"Play for value" is what falls out when the gain in win probability times the life swing, V(win) − V(loss), is smaller than the value given up. The engine still reports the mode it lands in, for analysis.

The loss side includes comeback money: losing a life to a blind adds $4 × all lives lost so far, timer deaths included, to that round's payout. Each loss pays more than the last even as each remaining life gets more precious, and V weighs both. The same applies to failing a normal blind.

Inputs to P(win):

- **Opponent model.** Each reveal (forced by turn order) shows their per-hand scoring power, combined with earlier PvP scores and the shop items both players saw.
- **Lives on both sides.** If the opponent is on one life, winning this PvP wins the game, so value play is almost never right.
- **Decaying jokers.** Conceding with fewer hands played preserves Ice Cream, Seltzer, and similar jokers.
- **Early win.** Value hands have to be played before the opponent finishes if you're ahead, since the blind ends then.

### Turn order

Turn order is an asset bought with early-hand score. Its worth comes from the decisive last hand: the leader sees the opponent's final total before committing; the trailer commits blind.

```latex
\Delta V_{\text{turn order}} = \mathbb{E}[V \mid \text{lead into last hand}] - \mathbb{E}[V \mid \text{trail into last hand}]
```

It is large when the race is close, when the best scoring hand and the best value hand differ, and when scoring is high-variance (Lucky cards, Bloodstone, Misprint). It is near zero when one player outscores the other by orders of magnitude.

For early hands, candidate plays are points in score-versus-value space, and the lead threshold is the cumulative score needed to be ahead. Seek the lead with the highest-value play past the threshold when P(gaining the lead) × the turn-order value exceeds the value given up. The cheapest lead-winning hand is usually not the max hand, which is why fighting for turn order and saving the big hand for last rarely conflict.

The actual cards still matter. A big last hand that needs specific cards can be ruined by scoring early. Jokers also shape the natural order: DNA and Sixth Sense reward the first hand; Acrobat and Dusk reward the last; Green Joker, Ride the Bus, and Hiker make later hands stronger.

### Shadow prices

Calling the full value network at every leaf of an in-round search is too slow. A network head outputs the marginal value of each resource in the current state: $1 (with interest steps), one tarot, one planet level per poker hand, a life for each player, a remaining hand, and each joker counter. These prices are where game phase, lives, and jokers enter the in-round decision.

The in-round solver:

1. Generates candidate plays and discards.
2. Simulates each against sampled draws and records the full resource outcome.
3. Drops lines beaten on every dimension by another line.
4. Ranks the rest by shadow-price-weighted value, then reranks the top few with the full value network.

Before the network is trained, hand-tuned prices from expert heuristics bootstrap the solver.

## Architecture

The engine has five parts: a simulator, a bridge to the real game, an encoder network with five output heads, a search layer, and a training loop that feeds self-play games back into the network.

&#91;embedded content: engine architecture · environment, network, search\]

The real game and the simulator sit behind one interface, so the same agent trains in simulation and plays through BalatroBot. Search is the only part that picks actions; the heads feed it.

### Simulator

The real game is far too slow for reinforcement learning, so the simulator is a Rust core with Python bindings (PyO3 and maturin). It has three layers:

1. **RNG.** A reimplementation of Balatro's seeded random streams, cross-checked against existing seed tools ([Immolate](https://github.com/OceanRamen/Immolate), Motely, The Soul) for shops, packs, tags, and bosses.
2. **Rules engine.** Blinds, hands, the scoring pipeline, and every joker, consumable, voucher, tag, deck, and stake. Content is written as data specs plus per-effect code hooks, versioned by game version, so a content update means new specs rather than a rewrite.
3. **MLBA layer.** PvP blinds, lives, comeback money, the PvP protocol, voucher and Bloodstone sync. The timer is not simulated, since self-play has no wall clock; the live bridge handles it (see Timer protocol).

State is a pure function of seed, deck, stake, and action history. Every state hashes, and a replay file is just those inputs plus the action list.

### Observations and actions

In play mode the agent sees its own full state: jokers in order with editions and counters, hand, remaining deck composition, consumables, vouchers, hand levels, money, ante, hands and discards, the shop and reroll cost, tags, both players' lives, the opponent's PvP score history, whether a timer is counting down on it, and who must play under the protocol. It does not see draw order, the opponent's build, the seed, or future shop items. Analysis mode adds the seed and the opponent's recorded PvP scores.

| Phase | Actions |
| --- | --- |
| Blind select | Play the blind, or skip it for the tag |
| In a blind | Select up to 5 cards and play or discard; use a consumable on targets; sell; reorder jokers |
| PvP blind | Everything above, plus wait |
| Shop | Buy a card, voucher, or pack; reroll; sell; use a consumable; reorder jokers; leave |
| Pack | Pick a card (with targets) or skip |

The simulator's legal-move generator supplies an action mask at every step.

### Model

An entity transformer encodes the state. Each joker (with its position, since order matters for xMult), playing card, consumable, shop item, voucher, tag, and poker-hand level is one token. A global token carries money, ante, hands, discards, lives, deck, stake, and opponent signals. All score quantities are stored as log10.

| Head | Output | Used by |
| --- | --- | --- |
| Policy | Action type, then targets; card subsets one card at a time with a stop token | Search priors, fast rollouts |
| Value | P(win game) | Search leaves, end-state evaluation |
| Score forecast | Quantiles of log10 score in the next PvP | PvP decisions, sandbagging |
| Opponent model | Opponent's likely jokers and per-hand scoring power | P(win) in PvP |
| Shadow prices | Marginal value of each resource now | Fast in-round solver |

Start small (around 6 layers, width 256) and grow only when evaluation says the network is the bottleneck.

### Opponent model

Both players see the same start of each ante's shop queue, so the items the opponent could have bought are largely known. The model combines that with their PvP scores, the per-hand reveals forced by turn order, and their lives. It trains by supervised learning on self-play games, where the opponent's true build is available.

### Search

- **In a blind:** sample shuffles consistent with the known remaining deck, score candidate plays exactly, prune dominated lines, and rank by shadow prices with a value-network rerank of the top few.
- **PvP:** work backward over both scores, both hand counts, and who must play, using the opponent model's score distributions. Hand 1 is a simultaneous decision against their hand-1 distribution.
- **Shop and blind select:** the policy proposes its top few options, unseen shop contents are sampled, and the value network judges the results (Gumbel AlphaZero / Stochastic MuZero style).
- **Analysis mode:** with the seed known, futures are deterministic given actions, so beam search over action sequences with the value network as the heuristic finds the best line against the opponent's recorded scores.

### Game bridge

[BalatroBot](https://pypi.org/project/balatrobot/) is a mod that serves a JSON-RPC API for reading state and taking actions in the real game. The bridge uses it for differential testing against the simulator and for live play. Running it alongside the Multiplayer mod, and reading the opponent's PvP score through it, still needs testing.

## Training and evaluation

Training runs in four stages, each gated by an evaluation that must pass before the next starts.

1. **Behavior cloning (optional bootstrap).** Train the policy on human action logs. Check what the mod repo's `replays` directory records, and ask the mod team about anonymized ranked logs. Parsing VODs is a last resort.
2. **Single-player RL.** PPO with action masking on vanilla runs. Curriculum: Red Deck at White Stake, up to Gold Stake, then all decks.
3. **MLBA self-play league.** Two agents play the same seed under the full protocol. The league holds the current agent, frozen snapshots, and exploiters (always sandbag, max economy, all-in early). Recorded PvP score traces can be replayed as cheap "ghost" opponents, mixed with live opponents so the agent learns to react inside a PvP blind.
4. **Search in the loop.** Search-improved action choices become policy targets, AlphaZero-style.

| Head | Training target |
| --- | --- |
| Policy | Search visit distribution (stage 4) or PPO objective (stages 2 and 3) |
| Value | Game outcome |
| Score forecast | Realized PvP score |
| Opponent model | Opponent's true build, available in self-play |
| Shadow prices | Value-network differences per resource, distilled |

**Evaluation**

- **Same-seed pairing.** Both sides play the same seed, so much of the luck cancels, as in duplicate bridge. Ratings between versions settle in fewer games.
- **Baselines.** Random legal moves, greedy max-score, and a scripted bot encoding common human rules.
- **Single-player benchmark.** Win rate by deck and stake on fixed seed sets.
- **Rule checks and diagnostics.** Pass/fail tests cover only rules and etiquette: legal moves, the PvP and timer protocols, playing promptly when behind, masking the opponent's hand-1 score. Strategic choices (scoring versus value hands, holding Gold cards, when to concede a PvP) have no fixed right answer, so they are tracked as scenario diagnostics for review, never as tests that would push the agent toward hand-written rules.
- **Humans.** Private lobbies with consenting players only.

## Milestones

Each milestone ends with a test that must pass before the next one starts. The numeric targets are starting points to revise once real measurements exist.

| Milestone | Delivers | Exit criterion |
| --- | --- | --- |
| M0 Setup | Repo, toolchain, modded game with BalatroBot, trace recorder | A full real-game run recorded as states and actions |
| M1 Scoring engine | Hand evaluation and the full scoring pipeline: chips, mult, xMult, retriggers, editions, enhancements, seals, scoring jokers | Matches the real game on 1,000+ recorded hands with zero mismatches |
| M2 RNG and generation | Seeded streams for shops, packs, tags, bosses, vouchers | Matches seed tools and the real game for Antes 1–8 on 1,000 seeds |
| M3 Single-player simulator | Every action, round, shop, and pack rule | 200 real-game traces replay with zero state differences; 100+ scripted-policy games per second per core |
| M4 In-round solver | End-state objective, value triggers, hand-tuned shadow prices | More money at cash-out than greedy max-score with no rise in blind failures over 10,000 sampled rounds; scenario diagnostics reviewed |
| M5 MLBA layer | PvP blinds, lives, protocol, voucher and Bloodstone sync, two-player environment | Protocol unit tests pass; 10,000 same-seed scripted games finish with no illegal state |
| M6 Agent v1 | Single-player PPO, then the self-play league | Wins 70%+ of same-seed games against the scripted bot |
| M7 Analysis mode | Known-seed best-line search, P(win) from broadcast-visible state | Produces a best line for recorded games where the seed is known |

## Open questions and risks

**Open questions**

- [ ] What happens on an exact final PvP tie?
- [ ] Are rewards still paid on a PvP loss in Season 4?
- [ ] Exact voucher sync, Bloodstone sync, and Idol fix logic (read the mod code).
- [ ] Does the mod show the opponent's hands remaining during a PvP blind?
- [ ] Can BalatroBot run alongside the Multiplayer mod and expose the opponent's PvP score?
- [ ] Can the live bridge start the Multiplayer mod's timer, or does that need a small extension?
- [ ] Does the timer restart after hitting 0, so it can cost more than one life in an ante?
- [ ] Do only the starting player's skips extend the timer?
- [ ] Are seeds recoverable after an MLBA game, for analysis mode?
- [ ] Does the mod repo's `replays` directory record usable action logs?

**Risks**

| Risk | Mitigation |
| --- | --- |
| One wrong RNG call desyncs everything after it | Diff full state after every action, not just at the end |
| Long tail of content and interactions (Blueprint and Brainstorm copying, retrigger order) | Per-joker golden tests and a coverage report |
| A content update to the base game | Content specs versioned by game version |
| League training needs more compute than a laptop | Single-player stages on CPU; rent GPUs for the league |
| Licensing | Game code and assets never enter the repo; the extracted Lua stays outside it |
| Fair play | No use in ranked or MLBA; ranked rules ban debug mode and unapproved mods ([rules](https://balatromp.com/docs/ranked-matchmaking/Ranked-rules)) |

## References

- [Major League Balatro — Season 4 About](https://majorleaguebalatro.com/about)
- [Major and Minor League ruleset — Balatro Multiplayer docs](https://balatromp.com/docs/rulesets/Major-and-Minor-league)
- [Ranked FAQ (The Order) — Balatro Multiplayer docs](https://balatromp.com/docs/ranked-matchmaking/faq)
- [Ranked rules — Balatro Multiplayer docs](https://balatromp.com/docs/ranked-matchmaking/Ranked-rules)
- [BalatroMultiplayer repository](https://github.com/Balatro-Multiplayer/BalatroMultiplayer) and [releases](https://github.com/Balatro-Multiplayer/BalatroMultiplayer/releases)
- [Balatro Shop Predictor — Balatro HQ](https://balatrohq.com/tools/shop-replay/)
- [Balatro But Multiplayer — Set Side B](https://setsideb.com/?p=10430)
- [MLBA Season 3 Grand Finals — Set Side B](https://setsideb.com/tag/balatromultiplayer/)
- [Immolate](https://github.com/OceanRamen/Immolate)
- [awesome-balatro tool list](https://github.com/jie65535/awesome-balatro)
- [BalatroBot](https://pypi.org/project/balatrobot/)
