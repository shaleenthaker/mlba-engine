"""Detect the installed game, Steamodded, and BalatroBot versions for trace headers."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

UNKNOWN = "unknown"


def balatro_dir() -> Path:
    if env := os.environ.get("BALATRO_DATA_DIR"):
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Balatro"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Balatro"
    return Path.home() / ".local/share/Balatro"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def detect_versions() -> dict[str, str]:
    mods = balatro_dir() / "Mods"

    smods = UNKNOWN
    if text := _read(mods / "smods" / "version.lua"):
        if m := re.search(r'"([^"]+)"', text):
            smods = m.group(1)

    # The 1.5.2 release left balatrobot.json at 1.5.1, so prefer pyproject.toml.
    balatrobot = UNKNOWN
    for d in sorted(mods.glob("balatrobot*")) if mods.is_dir() else []:
        if (text := _read(d / "pyproject.toml")) and (
            m := re.search(r'^version = "([^"]+)"', text, re.M)
        ):
            balatrobot = m.group(1)
            break
        if text := _read(d / "balatrobot.json"):
            balatrobot = json.loads(text).get("version", UNKNOWN)
            break

    game = UNKNOWN
    if text := _read(mods / "lovely" / "dump" / "globals.lua"):
        if m := re.search(r"VERSION = '([^']+)'", text):
            game = m.group(1)

    return {"game_version": game, "smods_version": smods, "balatrobot_version": balatrobot}
