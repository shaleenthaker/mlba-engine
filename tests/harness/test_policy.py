import copy
import json
from pathlib import Path

import pytest

from harness.models import GameState
from harness.policy import SimplePolicy

API_FIXTURES = Path(__file__).parents[1] / "fixtures" / "api"


def state(name, **edits):
    raw = json.loads((API_FIXTURES / f"{name}.json").read_text())
    raw.update(edits)
    return GameState.from_raw(raw)


def hand_of(keys, discards_left=3, hands_left=4):
    raw = copy.deepcopy(json.loads((API_FIXTURES / "selecting_hand.json").read_text()))
    template = raw["hand"]["cards"][0]
    cards = []
    for k in keys:
        c = copy.deepcopy(template)
        suit, rank = k.split("_")
        c.update(key=k)
        c["value"].update(suit=suit, rank=rank)
        cards.append(c)
    raw["hand"]["cards"] = cards
    raw["hand"]["count"] = len(cards)
    raw["round"].update(discards_left=discards_left, hands_left=hands_left)
    return GameState.from_raw(raw)


@pytest.mark.parametrize(
    "name,method",
    [("blind_select", "select"), ("round_eval", "cash_out"), ("booster_opened", "pack")],
)
def test_phase_actions(name, method):
    assert SimplePolicy().choose(state(name)).method == method


def test_game_over_is_terminal():
    assert SimplePolicy().choose(state("game_over")) is None


def test_won_is_terminal():
    assert SimplePolicy().choose(state("round_eval", won=True)) is None


def test_shop_buys_affordable_joker_then_leaves():
    shop = state("shop")
    raw = copy.deepcopy(shop.raw)
    joker = copy.deepcopy(raw["shop"]["cards"][0])
    joker.update(key="j_joker", set="JOKER")
    joker["cost"]["buy"] = 2
    raw["shop"]["cards"] = [raw["shop"]["cards"][0], joker]
    raw["money"] = 5
    action = SimplePolicy().choose(GameState.from_raw(raw))
    assert (action.method, action.params) == ("buy", {"card": 1})
    raw["money"] = 1
    assert SimplePolicy().choose(GameState.from_raw(raw)).method == "next_round"
    raw["money"] = 5
    raw["jokers"]["count"] = raw["jokers"]["limit"]
    assert SimplePolicy().choose(GameState.from_raw(raw)).method == "next_round"


def test_plays_flush():
    gs = hand_of(["H_2", "H_9", "S_3", "H_K", "H_4", "C_5", "H_7", "D_8"])
    a = SimplePolicy().choose(gs)
    assert a.method == "play"
    assert sorted(a.params["cards"]) == [0, 1, 3, 4, 6]


def test_plays_pairs_together():
    gs = hand_of(["H_2", "S_9", "C_9", "H_K", "D_K", "C_5", "H_7", "D_8"])
    a = SimplePolicy().choose(gs)
    assert a.method == "play"
    assert sorted(a.params["cards"]) == [1, 2, 3, 4]


def test_discards_low_cards_without_pair():
    gs = hand_of(["H_2", "S_9", "C_J", "H_K", "D_A", "C_5", "H_7", "D_3"])
    a = SimplePolicy().choose(gs)
    assert a.method == "discard"
    assert sorted(a.params["cards"]) == [0, 1, 5, 6, 7]


def test_plays_high_card_when_out_of_discards():
    gs = hand_of(["H_2", "S_9", "C_J", "H_K", "D_A", "C_5", "H_7", "D_3"], discards_left=0)
    a = SimplePolicy().choose(gs)
    assert (a.method, a.params) == ("play", {"cards": [4]})


def test_deterministic():
    gs = state("selecting_hand")
    assert SimplePolicy().choose(gs) == SimplePolicy().choose(gs)
