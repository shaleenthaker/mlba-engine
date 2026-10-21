"""Typed JSON-RPC client for BalatroBot (https://github.com/coder/balatrobot).

One method per endpoint. Methods that change the game return a GameState;
`call` is the untyped escape hatch the trace recorder and replayer use.
"""

from __future__ import annotations

import itertools
from typing import Any, Literal

import httpx

from harness.models import GameState

Deck = Literal[
    "RED", "BLUE", "YELLOW", "GREEN", "BLACK", "MAGIC", "NEBULA", "GHOST",
    "ABANDONED", "CHECKERED", "ZODIAC", "PAINTED", "ANAGLYPH", "PLASMA", "ERRATIC",
]  # fmt: skip
Stake = Literal["WHITE", "RED", "GREEN", "BLACK", "BLUE", "PURPLE", "ORANGE", "GOLD"]
Seal = Literal["RED", "BLUE", "GOLD", "PURPLE"]
Edition = Literal["HOLO", "FOIL", "POLYCHROME", "NEGATIVE"]
Enhancement = Literal["BONUS", "MULT", "WILD", "GLASS", "STEEL", "STONE", "GOLD", "LUCKY"]

DEFAULT_URL = "http://127.0.0.1:12346"


class BalatroBotError(Exception):
    def __init__(self, method: str, code: int, message: str, name: str | None):
        super().__init__(f"{method}: {name or code}: {message}")
        self.method = method
        self.code = code
        self.message = message
        self.name = name


class InternalError(BalatroBotError):
    pass


class BadRequest(BalatroBotError):
    pass


class InvalidState(BalatroBotError):
    pass


class NotAllowed(BalatroBotError):
    pass


_ERRORS: dict[int, type[BalatroBotError]] = {
    -32000: InternalError,
    -32001: BadRequest,
    -32002: InvalidState,
    -32003: NotAllowed,
}


def _params(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


def _exactly_one(method: str, params: dict[str, Any]) -> dict[str, Any]:
    if len(params) != 1:
        raise ValueError(f"{method} takes exactly one of its targets, got {sorted(params)}")
    return params


class BalatroBotClient:
    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._http = httpx.Client(base_url=url, timeout=timeout, transport=transport)
        self._ids = itertools.count(1)

    @classmethod
    def on_port(cls, port: int, **kwargs: Any) -> BalatroBotClient:
        return cls(url=f"http://127.0.0.1:{port}", **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BalatroBotClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send one JSON-RPC request and return its raw result."""
        req_id = next(self._ids)
        resp = self._http.post(
            "/", json={"jsonrpc": "2.0", "method": method, "params": params or {}, "id": req_id}
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            err = body["error"]
            name = (err.get("data") or {}).get("name")
            exc = _ERRORS.get(err.get("code"), BalatroBotError)
            raise exc(method, err.get("code"), err.get("message", ""), name)
        return body["result"]

    def _state(self, method: str, params: dict[str, Any] | None = None) -> GameState:
        return GameState.from_raw(self.call(method, params))

    # -- Session -----------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self.call("health")

    def gamestate(self) -> GameState:
        return self._state("gamestate")

    def start(self, deck: Deck, stake: Stake, seed: str | None = None) -> GameState:
        return self._state("start", _params(deck=deck, stake=stake, seed=seed))

    def menu(self) -> GameState:
        return self._state("menu")

    def save(self, path: str) -> dict[str, Any]:
        return self.call("save", {"path": path})

    def load(self, path: str) -> dict[str, Any]:
        return self.call("load", {"path": path})

    def screenshot(self, path: str) -> dict[str, Any]:
        return self.call("screenshot", {"path": path})

    # -- Blind select ------------------------------------------------------

    def select(self) -> GameState:
        return self._state("select")

    def skip(self) -> GameState:
        return self._state("skip")

    # -- In a blind --------------------------------------------------------

    def play(self, cards: list[int]) -> GameState:
        return self._state("play", {"cards": cards})

    def discard(self, cards: list[int]) -> GameState:
        return self._state("discard", {"cards": cards})

    def rearrange(
        self,
        hand: list[int] | None = None,
        jokers: list[int] | None = None,
        consumables: list[int] | None = None,
    ) -> GameState:
        params = _params(hand=hand, jokers=jokers, consumables=consumables)
        return self._state("rearrange", _exactly_one("rearrange", params))

    def use(self, consumable: int, cards: list[int] | None = None) -> GameState:
        return self._state("use", _params(consumable=consumable, cards=cards))

    def sell(self, joker: int | None = None, consumable: int | None = None) -> GameState:
        params = _params(joker=joker, consumable=consumable)
        return self._state("sell", _exactly_one("sell", params))

    # -- Round end and shop ------------------------------------------------

    def cash_out(self) -> GameState:
        return self._state("cash_out")

    def buy(
        self, card: int | None = None, voucher: int | None = None, pack: int | None = None
    ) -> GameState:
        params = _params(card=card, voucher=voucher, pack=pack)
        return self._state("buy", _exactly_one("buy", params))

    def reroll(self) -> GameState:
        return self._state("reroll")

    def next_round(self) -> GameState:
        return self._state("next_round")

    def pack(
        self, card: int | None = None, targets: list[int] | None = None, skip: bool | None = None
    ) -> GameState:
        if (card is None) == (not skip):
            raise ValueError("pack takes exactly one of card or skip=True")
        return self._state("pack", _params(card=card, targets=targets, skip=skip or None))

    # -- Debug (scenario building) -------------------------------------------

    def add(
        self,
        key: str,
        seal: Seal | None = None,
        edition: Edition | None = None,
        enhancement: Enhancement | None = None,
        eternal: bool | None = None,
        perishable: int | None = None,
        rental: bool | None = None,
    ) -> GameState:
        return self._state(
            "add",
            _params(
                key=key,
                seal=seal,
                edition=edition,
                enhancement=enhancement,
                eternal=eternal,
                perishable=perishable,
                rental=rental,
            ),
        )

    def set(
        self,
        money: int | None = None,
        chips: int | None = None,
        ante: int | None = None,
        round: int | None = None,
        hands: int | None = None,
        discards: int | None = None,
        shop: bool | None = None,
    ) -> GameState:
        params = _params(
            money=money, chips=chips, ante=ante, round=round, hands=hands, discards=discards, shop=shop
        )
        if not params:
            raise ValueError("set needs at least one value")
        return self._state("set", params)
