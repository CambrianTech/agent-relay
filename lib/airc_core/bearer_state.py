"""Helpers for reading bearer state JSON from shell commands."""

from __future__ import annotations

import json
import sys
from typing import Any


def _int_ts(value: Any) -> int:
    if value is None:
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m airc_core.bearer_state <state.json>", file=sys.stderr)
        return 2
    try:
        with open(args[0], "r", encoding="utf-8") as f:
            state = json.load(f)
    except OSError:
        return 1
    except json.JSONDecodeError:
        return 1
    print(f"{_int_ts(state.get('last_recv_ts'))} {_int_ts(state.get('last_heartbeat_ts'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
