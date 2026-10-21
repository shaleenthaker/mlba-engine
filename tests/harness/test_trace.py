import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harness.trace import FORMAT_VERSION, Step, TraceHeader, read_trace, write_trace

HEADER = TraceHeader(
    seed="ABC",
    deck="RED",
    stake="WHITE",
    game_version="1.0.1o",
    smods_version="26.1002.0",
    balatrobot_version="1.5.2",
    policy="simple-v1",
)

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(st.text(max_size=5), children, max_size=3),
    max_leaves=10,
)


@pytest.mark.parametrize("suffix", [".jsonl", ".jsonl.gz"])
def test_round_trip(tmp_path, suffix):
    steps = [
        Step(i=0, action={"method": "start", "params": {"seed": "ABC"}}, state_before=None, state_after={"a": 1}),
        Step(i=1, action={"method": "select", "params": {}}, state_before={"a": 1}, state_after={"a": 2}),
    ]
    path = tmp_path / f"t{suffix}"
    write_trace(path, HEADER, steps)
    header, read = read_trace(path)
    assert header == HEADER
    assert header.format_version == FORMAT_VERSION
    assert read == steps


def test_header_line_comes_first(tmp_path):
    path = tmp_path / "t.jsonl"
    write_trace(path, HEADER, [])
    first = json.loads(path.read_text().splitlines()[0])
    assert first["type"] == "header"
    assert first["seed"] == "ABC"


def test_missing_header_rejected(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"type": "step", "i": 0}) + "\n")
    with pytest.raises(ValueError):
        read_trace(path)


def test_non_contiguous_steps_rejected(tmp_path):
    path = tmp_path / "t.jsonl"
    write_trace(
        path,
        HEADER,
        [Step(i=0, action={"method": "select", "params": {}}, state_before={}, state_after={})],
    )
    with path.open("a") as f:
        f.write(json.dumps({"type": "step", "i": 5, "action": {"method": "select", "params": {}}, "state_before": {}, "state_after": {}}) + "\n")
    with pytest.raises(ValueError):
        read_trace(path)


@given(before=json_values, after=json_values)
def test_round_trip_arbitrary_states(tmp_path_factory, before, after):
    path = tmp_path_factory.mktemp("t") / "t.jsonl.gz"
    steps = [Step(i=0, action={"method": "play", "params": {"cards": [0]}}, state_before=before, state_after=after)]
    write_trace(path, HEADER, steps)
    assert read_trace(path) == (HEADER, steps)
