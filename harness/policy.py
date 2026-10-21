"""A deterministic scripted policy for recording traces.

This exists only to drive the real game through every phase for trace
recording. It is not strategy for the agent and nothing learns from it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from harness.models import Card, GameState

RANK_ORDER = "23456789TJQKA"


@dataclass(frozen=True)
class Action:
    method: str
    params: dict[str, Any] = field(default_factory=dict)


def _rank(card: Card) -> int:
    r = card.value.rank
    return RANK_ORDER.index(r) if r in RANK_ORDER else -1


class SimplePolicy:
    """Plays the blind, plays flushes or rank groups, buys affordable jokers."""

    name = "simple-v1"

    def choose(self, gs: GameState) -> Action | None:
        if gs.won or gs.state == "GAME_OVER":
            return None
        match gs.state:
            case "BLIND_SELECT":
                return Action("select")
            case "SELECTING_HAND":
                return self._hand(gs)
            case "ROUND_EVAL":
                return Action("cash_out")
            case "SHOP":
                return self._shop(gs)
            case "SMODS_BOOSTER_OPENED":
                return Action("pack", {"skip": True})
        raise ValueError(f"no policy for state {gs.state}")

    def _hand(self, gs: GameState) -> Action:
        cards = gs.hand.cards
        idx = list(range(len(cards)))

        by_suit = Counter(c.value.suit for c in cards if c.value.suit)
        if by_suit:
            suit, n = max(by_suit.items(), key=lambda kv: (kv[1], kv[0]))
            if n >= 5:
                same = [i for i in idx if cards[i].value.suit == suit]
                best = sorted(same, key=lambda i: (-_rank(cards[i]), i))[:5]
                return Action("play", {"cards": sorted(best)})

        by_rank = Counter(_rank(c) for c in cards)
        groups = sorted(
            (r for r, n in by_rank.items() if n >= 2 and r >= 0),
            key=lambda r: (-by_rank[r], -r),
        )
        if groups:
            play: list[int] = []
            for r in groups:
                members = [i for i in idx if _rank(cards[i]) == r]
                if len(play) + len(members) <= 5:
                    play += members
            if not play:
                play = [i for i in idx if _rank(cards[i]) == groups[0]][:5]
            return Action("play", {"cards": sorted(play)})

        if (gs.round.discards_left or 0) > 0:
            low = sorted(idx, key=lambda i: (_rank(cards[i]), i))[:5]
            return Action("discard", {"cards": sorted(low)})

        high = max(idx, key=lambda i: (_rank(cards[i]), -i))
        return Action("play", {"cards": [high]})

    def _shop(self, gs: GameState) -> Action:
        if gs.jokers is not None and not gs.jokers.full and gs.shop is not None:
            for i, c in enumerate(gs.shop.cards):
                if c.set == "JOKER" and c.cost.buy <= gs.money:
                    return Action("buy", {"card": i})
        return Action("next_round")
