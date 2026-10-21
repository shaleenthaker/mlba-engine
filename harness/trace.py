"""Trace files: one JSONL line per action, after a header line.

Line 1:  {"type": "header", format_version, seed, deck, stake, versions, policy}
Line n:  {"type": "step", i, action: {method, params}, state_before, state_after}

States are BalatroBot gamestate responses exactly as sent (ids included);
compare them with harness.canonical. The first step is always `start`, whose
state_before is null because the menu keeps stale data from earlier runs.
Paths ending in .gz are gzip-compressed.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, Any

FORMAT_VERSION = 1


@dataclass(frozen=True)
class TraceHeader:
    seed: str
    deck: str
    stake: str
    game_version: str
    smods_version: str
    balatrobot_version: str
    policy: str
    format_version: int = FORMAT_VERSION


@dataclass
class Step:
    i: int
    action: dict[str, Any]
    state_before: dict[str, Any] | None
    state_after: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


def _open(path: Path, mode: str) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8")
    return path.open(mode, encoding="utf-8")


def _dump(obj: dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n"


class TraceWriter:
    """Appends steps as they happen, so a crash mid-run keeps what was recorded."""

    def __init__(self, path: str | Path, header: TraceHeader):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = _open(self.path, "w")
        self._f.write(_dump({"type": "header", **asdict(header)}))
        self._next = 0

    def write(self, step: Step) -> None:
        if step.i != self._next:
            raise ValueError(f"step {step.i} written out of order (expected {self._next})")
        record = {"type": "step", **asdict(step)}
        if not step.extra:
            del record["extra"]
        self._f.write(_dump(record))
        self._f.flush()
        self._next += 1

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def write_trace(path: str | Path, header: TraceHeader, steps: Iterable[Step]) -> None:
    with TraceWriter(path, header) as w:
        for s in steps:
            w.write(s)


def read_trace(path: str | Path) -> tuple[TraceHeader, list[Step]]:
    with _open(Path(path), "r") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    if not lines or lines[0].get("type") != "header":
        raise ValueError(f"{path}: first line is not a trace header")
    head = {k: v for k, v in lines[0].items() if k != "type"}
    header = TraceHeader(**head)
    if header.format_version != FORMAT_VERSION:
        raise ValueError(f"{path}: unsupported format_version {header.format_version}")
    steps = []
    for n, rec in enumerate(lines[1:]):
        if rec.get("type") != "step" or rec.get("i") != n:
            raise ValueError(f"{path}: line {n + 2} is not step {n}")
        steps.append(
            Step(
                i=rec["i"],
                action=rec["action"],
                state_before=rec["state_before"],
                state_after=rec["state_after"],
                extra=rec.get("extra", {}),
            )
        )
    return header, steps
