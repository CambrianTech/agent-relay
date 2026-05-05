"""Append local airc system events to messages.jsonl."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _channels(config_path: str) -> list[str]:
    try:
        with open(config_path, encoding="utf-8") as f:
            channels = json.load(f).get("subscribed_channels")
        if isinstance(channels, list):
            cleaned = [str(ch).lstrip("#") for ch in channels if str(ch).strip()]
            if cleaned:
                return cleaned
    except Exception:
        pass
    return ["general"]


def append_join(home: str, name: str, client_id: str = "") -> int:
    channels = _channels(os.path.join(home, "config.json"))
    os.makedirs(home, exist_ok=True)
    log_path = os.path.join(home, "messages.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        for channel in channels:
            event = {
                "ts": _timestamp(),
                "from": "airc",
                "to": "all",
                "channel": channel,
                "msg": f"{name} joined #{channel}",
            }
            if client_id:
                event["client_id"] = client_id
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.system_event")
    sub = parser.add_subparsers(dest="cmd", required=True)
    join = sub.add_parser("join")
    join.add_argument("--home", required=True)
    join.add_argument("--name", required=True)
    join.add_argument("--client-id", default="")
    args = parser.parse_args(argv)

    if args.cmd == "join":
        return append_join(args.home, args.name, args.client_id)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
