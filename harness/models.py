"""Pydantic models for BalatroBot 1.5.2 game state.

Field names and shapes follow BalatroBot's types.lua and openrpc.json, checked
against responses recorded in tests/fixtures/api/. Every model forbids extra
fields so an API change fails loudly instead of being silently dropped.

Lua's JSON encoder writes an empty table as `[]`, so object-typed fields
accept `[]` as an empty object.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, PrivateAttr


def _empty_list_as_dict(v: Any) -> Any:
    return {} if v == [] else v


LuaObject = BeforeValidator(_empty_list_as_dict)
Number = int | float


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CardValue(_Model):
    suit: str | None = None
    rank: str | None = None
    effect: str = ""


class CardModifier(_Model):
    seal: str | None = None
    edition: str | None = None
    # The game's ability.effect, uppercased. For playing cards this is the
    # enhancement; jokers and consumables carry their own effect class here
    # (for example "MULT" on Joker, "HAND UPGRADE" on planets).
    enhancement: str | None = None
    eternal: bool = False
    perishable: int | None = None
    rental: bool = False


class CardState(_Model):
    debuff: bool = False
    hidden: bool = False
    highlight: bool = False


class CardCost(_Model):
    sell: Number
    buy: Number


class Card(_Model):
    id: int
    key: str
    set: str
    label: str
    value: Annotated[CardValue, LuaObject]
    modifier: Annotated[CardModifier, LuaObject]
    state: Annotated[CardState, LuaObject]
    cost: Annotated[CardCost, LuaObject]


class Area(_Model):
    count: int
    limit: int
    highlighted_limit: int | None = None
    cards: list[Card]

    @property
    def full(self) -> bool:
        return self.count >= self.limit


class PokerHand(_Model):
    order: int
    level: int
    chips: Number
    mult: Number
    played: int
    played_this_round: int
    example: list[list[Any]]


class Round(_Model):
    hands_left: int | None = None
    hands_played: int | None = None
    discards_left: int | None = None
    discards_used: int | None = None
    reroll_cost: int | None = None
    chips: Number | None = None


class Blind(_Model):
    type: str
    status: str
    name: str
    effect: str
    score: Number
    tag_name: str | None = None
    tag_effect: str | None = None


class Blinds(_Model):
    small: Blind
    big: Blind
    boss: Blind


class GameState(_Model):
    state: str
    round_num: int
    ante_num: int
    money: Number
    won: bool | None = None
    deck: str | None = None
    stake: str | None = None
    seed: str | None = None
    used_vouchers: Annotated[dict[str, str], LuaObject] = {}
    hands: Annotated[dict[str, PokerHand], LuaObject] = {}
    round: Annotated[Round, LuaObject] | None = None
    blinds: Annotated[Blinds, LuaObject] | None = None
    jokers: Area | None = None
    consumables: Area | None = None
    cards: Area | None = None
    hand: Area | None = None
    shop: Area | None = None
    vouchers: Area | None = None
    packs: Area | None = None
    pack: Area | None = None

    _raw: dict[str, Any] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> GameState:
        gs = cls.model_validate(raw)
        gs._raw = raw
        return gs

    @property
    def raw(self) -> dict[str, Any]:
        """The response exactly as the game sent it."""
        return self._raw
