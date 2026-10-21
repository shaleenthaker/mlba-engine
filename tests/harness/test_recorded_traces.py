"""Integrity checks on committed real-game traces. Runs without the game."""

from pathlib import Path

import pytest

from harness.canonical import diff
from harness.models import GameState
from harness.trace import read_trace

TRACES = sorted((Path(__file__).parents[1] / "fixtures" / "traces").glob("*.jsonl.gz"))


def test_at_least_one_trace():
    assert TRACES


@pytest.mark.parametrize("path", TRACES, ids=lambda p: p.name)
def test_trace_is_a_complete_consistent_run(path):
    header, steps = read_trace(path)
    assert header.game_version == "1.0.1o"
    assert header.smods_version == "26.1002.0"

    first = steps[0]
    assert first.action == {
        "method": "start",
        "params": {"deck": header.deck, "stake": header.stake, "seed": header.seed},
    }
    assert first.state_before is None
    assert first.state_after["seed"] == header.seed

    for prev, cur in zip(steps, steps[1:]):
        assert diff(prev.state_after, cur.state_before) == [], f"step {cur.i}"

    for step in steps:
        for state in (step.state_before, step.state_after):
            if state is not None:
                GameState.from_raw(state)

    last = steps[-1].state_after
    assert last["state"] == "GAME_OVER" or last.get("won")
