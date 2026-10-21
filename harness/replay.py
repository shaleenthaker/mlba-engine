"""Replay a trace through the real game and check every recorded state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from harness.canonical import diff, state_hash
from harness.recorder import Game, start_run
from harness.trace import read_trace


@dataclass
class Mismatch:
    step: int
    method: str
    which: str  # "state_before" or "state_after"
    paths: list[str]


@dataclass
class ReplayResult:
    steps: int = 0
    comparisons: int = 0
    mismatch: Mismatch | None = None
    hashes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.mismatch is None


def replay_trace(game: Game, path: str | Path) -> ReplayResult:
    """Stops at the first mismatch, since everything after it is suspect."""
    header, steps = read_trace(path)
    result = ReplayResult()
    for step in steps:
        method, params = step.action["method"], step.action["params"]
        if step.state_before is not None:
            if not _check(game, step.state_before, step.i, method, "state_before", result):
                return result
        if method == "start":
            start_run(game, params)
        else:
            game.call(method, params)
        if not _check(game, step.state_after, step.i, method, "state_after", result):
            return result
        result.steps += 1
    return result


def _check(game: Game, expected, i: int, method: str, which: str, result: ReplayResult) -> bool:
    actual = game.call("gamestate")
    result.comparisons += 1
    if paths := diff(expected, actual):
        result.mismatch = Mismatch(step=i, method=method, which=which, paths=paths)
        return False
    if which == "state_after":
        result.hashes.append(state_hash(actual))
    return True
