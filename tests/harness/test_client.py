import json
from pathlib import Path

import httpx
import pytest

from harness.client import (
    BadRequest,
    BalatroBotClient,
    BalatroBotError,
    InternalError,
    InvalidState,
    NotAllowed,
)
from harness.models import GameState

STATE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "api" / "selecting_hand.json").read_text()
)


def make_client(handler):
    return BalatroBotClient(transport=httpx.MockTransport(handler))


def ok(result):
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "result": result, "id": body["id"]})

    return handler


def test_request_shape_and_none_params_dropped():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return ok(STATE)(request)

    client = make_client(handler)
    client.start(deck="RED", stake="WHITE", seed="ABC")
    client.add(key="j_joker", edition="FOIL")
    client.select()
    assert seen[0]["jsonrpc"] == "2.0"
    assert seen[0]["method"] == "start"
    assert seen[0]["params"] == {"deck": "RED", "stake": "WHITE", "seed": "ABC"}
    assert seen[1]["params"] == {"key": "j_joker", "edition": "FOIL"}
    assert seen[2]["params"] == {}
    assert len({s["id"] for s in seen}) == 3


def test_typed_methods_return_gamestate():
    client = make_client(ok(STATE))
    gs = client.play([0, 1])
    assert isinstance(gs, GameState)
    assert gs.raw == STATE


def test_health():
    client = make_client(ok({"status": "ok"}))
    assert client.health() == {"status": "ok"}


@pytest.mark.parametrize(
    "code,name,exc",
    [
        (-32000, "INTERNAL_ERROR", InternalError),
        (-32001, "BAD_REQUEST", BadRequest),
        (-32002, "INVALID_STATE", InvalidState),
        (-32003, "NOT_ALLOWED", NotAllowed),
    ],
)
def test_errors_map_to_exceptions(code, name, exc):
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "error": {"code": code, "message": "nope", "data": {"name": name}},
                "id": body["id"],
            },
        )

    client = make_client(handler)
    with pytest.raises(exc) as info:
        client.select()
    assert isinstance(info.value, BalatroBotError)
    assert info.value.code == code
    assert info.value.method == "select"


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("buy", {}),
        ("buy", {"card": 0, "pack": 1}),
        ("sell", {}),
        ("rearrange", {"hand": [0], "jokers": [0]}),
        ("pack", {}),
    ],
)
def test_exactly_one_target_enforced(method, kwargs):
    client = make_client(ok(STATE))
    with pytest.raises(ValueError):
        getattr(client, method)(**kwargs)
