"""Collaboration health helpers.

Keep peer-record and recent-traffic interpretation out of bash. Shell
callers should ask this module for the user-facing lines instead of
embedding Python snippets inline.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional


RECENT_REMOTE_WINDOW_SEC = 600


@dataclass(frozen=True)
class RemoteActivity:
    name: str
    ts: int


def _epoch(ts: object) -> Optional[int]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return calendar.timegm(time.strptime(ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return None


def _fmt_age(ts: Optional[int], now: Optional[int] = None) -> str:
    if ts is None:
        return "never"
    if now is None:
        now = int(time.time())
    age = max(0, now - ts)
    if age < 60:
        return f"{age}s ago"
    if age < 3600:
        return f"{age // 60}m ago"
    if age < 86400:
        return f"{age // 3600}h ago"
    return f"{age // 86400}d ago"


def peer_record_count(home: str) -> int:
    peers_dir = os.path.join(home, "peers")
    if not os.path.isdir(peers_dir):
        return 0
    count = 0
    for entry in os.listdir(peers_dir):
        if not entry.endswith(".json"):
            continue
        try:
            with open(os.path.join(peers_dir, entry), encoding="utf-8") as f:
                json.load(f)
        except Exception:
            continue
        count += 1
    return count


def recent_remote_activity(home: str, my_name: str, window_sec: int = RECENT_REMOTE_WINDOW_SEC) -> Optional[RemoteActivity]:
    messages_log = os.path.join(home, "messages.jsonl")
    now = int(time.time())
    last: Optional[RemoteActivity] = None
    try:
        with open(messages_log, encoding="utf-8") as f:
            for line in f:
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                sender = msg.get("from")
                if not sender or sender in (my_name, "airc"):
                    continue
                ts = _epoch(msg.get("ts"))
                if ts is None:
                    continue
                if now - ts >= window_sec:
                    continue
                if last is None or ts > last.ts:
                    last = RemoteActivity(str(sender), ts)
    except OSError:
        pass
    return last


def recent_remote_speakers(home: str, my_name: str, window_sec: int = RECENT_REMOTE_WINDOW_SEC) -> dict[str, int]:
    messages_log = os.path.join(home, "messages.jsonl")
    now = int(time.time())
    speakers: dict[str, int] = {}
    try:
        with open(messages_log, encoding="utf-8") as f:
            for line in f:
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                sender = msg.get("from")
                if not sender or sender in (my_name, "airc"):
                    continue
                ts = _epoch(msg.get("ts"))
                if ts is None or now - ts >= window_sec:
                    continue
                speakers[str(sender)] = max(speakers.get(str(sender), 0), ts)
    except OSError:
        pass
    return speakers


def cmd_status(args: argparse.Namespace) -> int:
    count = peer_record_count(args.home)
    recent = recent_remote_activity(args.home, args.my_name)
    now = int(time.time())
    if recent is None:
        remote_desc = "no remote messages recorded"
    else:
        remote_desc = f"last remote message {max(0, now - recent.ts)}s ago from {recent.name}"

    if count == 0:
        if recent is not None:
            print(f"  collaboration: DEGRADED (0 peer records; {remote_desc})")
            print("    DMs/whois/peer targeting may be broken; broadcast traffic is flowing.")
        else:
            print(f"  collaboration: SOLO (0 peer records; {remote_desc})")
            print("    Sends may only land in this local/self-hosted gist until another agent joins this exact mesh.")
    else:
        print(f"  collaboration: ok ({count} peer record(s); {remote_desc})")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    count = peer_record_count(args.home)
    recent = recent_remote_activity(args.home, args.my_name)
    now = int(time.time())
    if count > 0:
        print(f"  [ok] collaboration mesh has {count} peer record(s)")
        return 0
    if recent is not None:
        print(
            f"  [WARN] collaboration mesh has 0 peer records, but remote traffic arrived "
            f"{max(0, now - recent.ts)}s ago from {recent.name}"
        )
        print("         Peer metadata is degraded (DMs/whois may fail), but this is NOT a solo island.")
        return 1
    print("  [BLOCKED] collaboration mesh has 0 peer records — local transport may be alive, but this is a solo island")
    print("         Check: airc peers; ask peers to run 'airc update --channel canary && airc connect <current invite>'")
    return 2


def cmd_send_warning(args: argparse.Namespace) -> int:
    if peer_record_count(args.home) > 0:
        return 0
    recent = recent_remote_activity(args.home, args.my_name)
    now = int(time.time())
    if recent is not None:
        print(
            f"  ⚠ collaboration: 0 peer records, but remote traffic arrived "
            f"{max(0, now - recent.ts)}s ago from {recent.name}; peer metadata degraded, bus is not solo.",
            file=sys.stderr,
        )
    else:
        print(
            "  ⚠ collaboration: 0 peer records in this scope; this may be a solo mesh. "
            "Run 'airc peers' and verify others joined this gist.",
            file=sys.stderr,
        )
    return 0


def cmd_peers_fallback(args: argparse.Namespace) -> int:
    speakers = recent_remote_speakers(args.home, args.my_name)
    if not speakers:
        return 1
    print("  No peer records yet, but recent remote traffic is visible:")
    for who, ts in sorted(speakers.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {who} → (broadcast-only)   [(from messages.jsonl)]   last seen {_fmt_age(ts)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.collaboration")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "doctor", "send-warning", "peers-fallback"):
        p = sub.add_parser(name)
        p.add_argument("--home", required=True)
        p.add_argument("--my-name", default="")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "send-warning":
        return cmd_send_warning(args)
    if args.cmd == "peers-fallback":
        return cmd_peers_fallback(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
