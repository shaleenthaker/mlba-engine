import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.models import GameState

API_FIXTURES = Path(__file__).parents[1] / "fixtures" / "api"
FIXTURE_FILES = sorted(API_FIXTURES.glob("*.json"))


def load(name):
    return json.loads((API_FIXTURES / f"{name}.json").read_text())


def test_fixtures_exist():
    names = {p.stem for p in FIXTURE_FILES}
    assert {
        "menu",
        "blind_select",
        "selecting_hand",
        "selecting_hand_modded",
        "round_eval",
        "shop",
        "booster_opened",
        "game_over",
    } <= names


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_every_recorded_state_validates(path):
    raw = json.loads(path.read_text())
    gs = GameState.from_raw(raw)
    assert gs.raw is raw
    assert gs.state == raw["state"]


def test_empty_lua_tables_are_empty_objects():
    gs = GameState.from_raw(load("selecting_hand"))
    card = gs.hand.cards[0]
    assert card.modifier.seal is None
    assert card.state.debuff is False
    assert gs.used_vouchers == {}


def test_modifiers_parse():
    gs = GameState.from_raw(load("selecting_hand_modded"))
    joker = gs.jokers.cards[0]
    assert joker.key == "j_joker"
    assert joker.modifier.edition == "POLYCHROME"
    ace = next(c for c in gs.hand.cards if c.key == "H_A" and c.modifier.seal)
    assert (ace.modifier.enhancement, ace.modifier.edition, ace.modifier.seal) == (
        "GLASS",
        "FOIL",
        "RED",
    )
    assert ace.value.rank == "A" and ace.value.suit == "H"


def test_shop_areas_present_only_in_shop():
    shop = GameState.from_raw(load("shop"))
    assert shop.shop is not None and shop.vouchers is not None and shop.packs is not None
    hand = GameState.from_raw(load("selecting_hand"))
    assert hand.shop is None


def test_unknown_field_is_rejected():
    raw = copy.deepcopy(load("selecting_hand"))
    raw["surprise"] = 1
    with pytest.raises(ValidationError):
        GameState.from_raw(raw)


def test_unknown_card_field_is_rejected():
    raw = copy.deepcopy(load("selecting_hand"))
    raw["hand"]["cards"][0]["surprise"] = 1
    with pytest.raises(ValidationError):
        GameState.from_raw(raw)
