import copy
import json
from pathlib import Path

import pytest

from harness.client import InternalError
from harness.recorder import record_run, start_run
from harness.replay import replay_trace
from harness.trace import read_trace

API_FIXTURES = Path(__file__).parents[1] / "fixtures" / "api"


def fixture(name):
    return json.loads((API_FIXTURES / f"{name}.json").read_text())


class ScriptedGame:
    """Fake game: a fixed sequence of states, advanced by each non-gamestate call."""

    def __init__(self, states, id_offset=0):
        self.states = [copy.deepcopy(s) for s in states]
        for s in self.states:
            for area in ("jokers", "consumables", "cards", "hand", "shop", "vouchers", "packs", "pack"):
                if isinstance(s.get(area), dict):
                    for card in s[area]["cards"]:
                        card["id"] += id_offset
        self.pos = 0
        self.calls = []

    def call(self, method, params=None):
        self.calls.append((method, params or {}))
        if method == "gamestate":
            return self.states[self.pos]
        if method == "menu":
            self.pos = 0
            return self.states[0]
        self.pos += 1
        return self.states[self.pos]


STATES = [fixture(n) for n in ("menu", "blind_select", "selecting_hand", "round_eval", "shop", "game_over")]


class FixedPolicy:
    name = "fixed"

    def __init__(self):
        self.plan = iter(["select", "play", "cash_out", "next_round"])

    def choose(self, gs):
        from harness.policy import Action

        if gs.state == "GAME_OVER":
            return None
        m = next(self.plan)
        return Action(m, {"cards": [0]} if m == "play" else {})


def record(tmp_path):
    path = tmp_path / "run.jsonl.gz"
    record_run(ScriptedGame(STATES), FixedPolicy(), path, seed="X", deck="RED", stake="WHITE")
    return path


def test_recorder_writes_every_action(tmp_path):
    header, steps = read_trace(record(tmp_path))
    assert header.seed == "X" and header.policy == "fixed"
    assert [s.action["method"] for s in steps] == ["start", "select", "play", "cash_out", "next_round"]
    assert steps[0].state_before is None
    assert steps[0].action["params"] == {"deck": "RED", "stake": "WHITE", "seed": "X"}
    for prev, cur in zip(steps, steps[1:]):
        assert cur.state_before == prev.state_after
    assert steps[-1].state_after["state"] == "GAME_OVER"


def test_replay_matches_with_different_ids(tmp_path):
    path = record(tmp_path)
    result = replay_trace(ScriptedGame(STATES, id_offset=1000), path)
    assert result.ok
    assert result.steps == 5
    assert result.comparisons == 9
    assert result.mismatch is None


class FlakyStart:
    def __init__(self, message, failures):
        self.message, self.failures, self.calls = message, failures, []

    def call(self, method, params=None):
        self.calls.append(method)
        if method == "start" and self.failures:
            self.failures -= 1
            raise InternalError("start", -32000, self.message, "INTERNAL_ERROR")
        return {}


def test_start_run_retries_menu_race(monkeypatch):
    monkeypatch.setattr("harness.recorder.time.sleep", lambda s: None)
    game = FlakyStart("attempt to index field 'viewed_back' (a nil value)", failures=2)
    start_run(game, {"deck": "RED", "stake": "WHITE", "seed": "X"})
    assert game.calls == ["menu", "start"] * 3


def test_start_run_raises_other_errors():
    game = FlakyStart("something else", failures=1)
    with pytest.raises(InternalError):
        start_run(game, {"deck": "RED", "stake": "WHITE", "seed": "X"})


def test_replay_reports_first_mismatch(tmp_path):
    path = record(tmp_path)
    changed = copy.deepcopy(STATES)
    changed[3]["money"] += 1
    result = replay_trace(ScriptedGame(changed), path)
    assert not result.ok
    assert result.mismatch.step == 2
    assert result.mismatch.which == "state_after"
    assert "money" in result.mismatch.paths
