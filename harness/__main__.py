"""Harness CLI.

    uv run python -m harness record --seed SEED [--deck RED] [--stake WHITE] --out PATH
    uv run python -m harness replay PATH
"""

from __future__ import annotations

import argparse
import sys
import time

from harness.client import BalatroBotClient
from harness.policy import SimplePolicy
from harness.recorder import record_run
from harness.replay import replay_trace
from harness.trace import read_trace


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harness")
    p.add_argument("--port", type=int, default=12346)
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="record one seeded run with the scripted policy")
    rec.add_argument("--seed", required=True)
    rec.add_argument("--deck", default="RED")
    rec.add_argument("--stake", default="WHITE")
    rec.add_argument("--out", required=True)

    rep = sub.add_parser("replay", help="replay a trace through the game and check every state")
    rep.add_argument("trace")

    args = p.parse_args(argv)
    with BalatroBotClient.on_port(args.port) as client:
        t0 = time.monotonic()
        if args.cmd == "record":
            n = record_run(client, SimplePolicy(), args.out, args.seed, args.deck, args.stake)
            _, steps = read_trace(args.out)
            last = steps[-1].state_after
            print(
                f"recorded {n} steps to {args.out} in {time.monotonic() - t0:.1f}s; "
                f"ended {last['state']} at ante {last['ante_num']} round {last['round_num']}"
            )
            return 0

        result = replay_trace(client, args.trace)
        took = time.monotonic() - t0
        if result.ok:
            print(
                f"OK: {result.steps} steps replayed, {result.comparisons} states compared, "
                f"0 mismatches ({took:.1f}s); final state hash {result.hashes[-1][:16]}"
            )
            return 0
        m = result.mismatch
        print(f"MISMATCH at step {m.step} ({m.method}), {m.which}; after {result.steps} matching steps")
        for path in m.paths:
            print(f"  {path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
