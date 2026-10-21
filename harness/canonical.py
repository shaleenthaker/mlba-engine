"""Canonical game state: compare by content and order, never by card id.

Card ids are the game's sort_id, which keeps counting across runs, so the
same seed gives different ids every time. Everything else is kept as sent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CARD_KEYS = frozenset({"id", "key", "set", "label", "value", "modifier", "state", "cost"})


def _is_card(d: dict[str, Any]) -> bool:
    return CARD_KEYS <= d.keys()


def canonical(state: Any) -> Any:
    """A copy of `state` with every card id removed."""
    if isinstance(state, dict):
        drop_id = _is_card(state)
        return {k: canonical(v) for k, v in state.items() if not (drop_id and k == "id")}
    if isinstance(state, list):
        return [canonical(v) for v in state]
    return state


def canonical_json(state: Any) -> str:
    return json.dumps(canonical(state), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def state_hash(state: Any) -> str:
    return hashlib.sha256(canonical_json(state).encode()).hexdigest()


def diff(a: Any, b: Any, limit: int = 50) -> list[str]:
    """Paths where the canonical forms of `a` and `b` differ, up to `limit`."""
    out: list[str] = []
    _diff(canonical(a), canonical(b), "", out, limit)
    return out


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _diff(a: Any, b: Any, path: str, out: list[str], limit: int) -> None:
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(a.keys() | b.keys()):
            if k not in a or k not in b:
                out.append(_join(path, k))
            else:
                _diff(a[k], b[k], _join(path, k), out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}[len {len(a)} != {len(b)}]")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b or type(a) is not type(b):
        out.append(path)
