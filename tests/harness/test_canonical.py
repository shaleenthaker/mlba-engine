import copy
import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from harness.canonical import canonical, diff, state_hash

STATE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "api" / "shop.json").read_text()
)
AREAS = ("jokers", "consumables", "cards", "hand", "shop", "vouchers", "packs")


def all_cards(state):
    for area in AREAS:
        if isinstance(state.get(area), dict):
            yield from state[area]["cards"]


def test_canonical_strips_every_card_id():
    c = canonical(STATE)
    assert list(all_cards(STATE))
    assert all("id" not in card for card in all_cards(c))


def test_canonical_does_not_mutate_input():
    before = copy.deepcopy(STATE)
    canonical(STATE)
    assert STATE == before


@given(st.integers(min_value=0, max_value=10**6))
def test_hash_ignores_card_ids(offset):
    other = copy.deepcopy(STATE)
    for card in all_cards(other):
        card["id"] += offset
    assert state_hash(other) == state_hash(STATE)


def test_hash_ignores_key_order():
    reordered = json.loads(json.dumps(STATE, sort_keys=False))
    reordered = dict(reversed(list(reordered.items())))
    assert state_hash(reordered) == state_hash(STATE)


def test_hash_sees_card_order():
    other = copy.deepcopy(STATE)
    other["cards"]["cards"].reverse()
    assert state_hash(other) != state_hash(STATE)


def test_hash_sees_content_change():
    other = copy.deepcopy(STATE)
    other["money"] += 1
    assert state_hash(other) != state_hash(STATE)


def test_diff_reports_paths():
    other = copy.deepcopy(STATE)
    other["money"] += 1
    other["cards"]["cards"][3]["value"]["rank"] = "Z"
    other["round"]["new_field"] = 1
    paths = diff(STATE, other)
    assert "money" in paths
    assert "cards.cards[3].value.rank" in paths
    assert "round.new_field" in paths
    assert diff(STATE, copy.deepcopy(STATE)) == []


def test_diff_ignores_ids():
    other = copy.deepcopy(STATE)
    for card in all_cards(other):
        card["id"] += 7
    assert diff(STATE, other) == []
