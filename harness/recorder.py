"""Record a seeded real-game run as a trace."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Protocol

from harness.canonical import diff
from harness.client import InternalError
from harness.models import GameState
from harness.policy import Action
from harness.trace import Step, TraceHeader, TraceWriter
from harness.versions import detect_versions


class Game(Protocol):
    def call(self, method: str, params: dict[str, Any] | None = None) -> Any: ...


class Policy(Protocol):
    name: str

    def choose(self, gs: GameState) -> Action | None: ...


class UnstableState(RuntimeError):
    """The game's state changed between two reads with no action in between."""


def start_run(game: Game, params: dict[str, Any], attempts: int = 10) -> None:
    """Go to the menu and start a run.

    BalatroBot's `menu` returns once the menu UI exists, which can be before
    the game sets G.GAME.viewed_back; a `start` sent in that gap fails with an
    INTERNAL_ERROR about viewed_back. Wait and retry from the menu.
    """
    for attempt in range(attempts):
        game.call("menu")
        try:
            game.call("start", params)
            return
        except InternalError as e:
            if "viewed_back" not in e.message or attempt == attempts - 1:
                raise
            time.sleep(0.25 * (attempt + 1))


def record_run(
    game: Game,
    policy: Policy,
    out: str | Path,
    seed: str,
    deck: str,
    stake: str,
    max_steps: int = 5000,
) -> int:
    """Play one run from the menu to game over (or a win). Returns steps written."""
    header = TraceHeader(seed=seed, deck=deck, stake=stake, policy=policy.name, **detect_versions())
    with TraceWriter(out, header) as w:
        start = Action("start", {"deck": deck, "stake": stake, "seed": seed})
        start_run(game, start.params)
        after = game.call("gamestate")
        w.write(Step(i=0, action=_action(start), state_before=None, state_after=after))

        n = 1
        while n < max_steps:
            before = game.call("gamestate")
            if paths := diff(after, before):
                raise UnstableState(f"state drifted before step {n}: {paths[:10]}")
            action = policy.choose(GameState.from_raw(before))
            if action is None:
                return n
            game.call(action.method, action.params)
            after = game.call("gamestate")
            w.write(Step(i=n, action=_action(action), state_before=before, state_after=after))
            n += 1
    raise RuntimeError(f"run did not end within {max_steps} steps")


def _action(a: Action) -> dict[str, Any]:
    return {"method": a.method, "params": dict(a.params)}
