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
    return _remote_activity(home, my_name, window_sec=window_sec)


def any_remote_activity(home: str, my_name: str) -> Optional[RemoteActivity]:
    return _remote_activity(home, my_name, window_sec=None)


def _remote_activity(home: str, my_name: str, window_sec: Optional[int]) -> Optional[RemoteActivity]:
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
                if window_sec is not None and now - ts >= window_sec:
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
    speakers = recent_remote_speakers(args.home, args.my_name)
    recent = recent_remote_activity(args.home, args.my_name)
    any_recent = recent if recent is not None else any_remote_activity(args.home, args.my_name)
    now = int(time.time())
    if any_recent is None:
        remote_desc = "no remote messages recorded"
    else:
        remote_desc = f"last remote message {max(0, now - any_recent.ts)}s ago from {any_recent.name}"

    if count == 0:
        if speakers:
            label = "broadcast peer" if len(speakers) == 1 else "broadcast peers"
            print(f"  collaboration: ok ({len(speakers)} {label}; 0 direct peer records; {remote_desc})")
            print("    Presence is derived from recent signed room traffic.")
        elif any_recent is None:
            print(f"  collaboration: waiting for peers (0 peer records; {remote_desc})")
            print("    First agent in a room is expected to be alone until another agent joins this gist.")
        else:
            print(f"  collaboration: SOLO (0 peer records; {remote_desc})")
            print("    Sends may only land in this local/self-hosted gist until another agent joins this exact mesh.")
    else:
        print(f"  collaboration: ok ({count} peer record(s); {remote_desc})")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    count = peer_record_count(args.home)
    speakers = recent_remote_speakers(args.home, args.my_name)
    recent = recent_remote_activity(args.home, args.my_name)
    any_recent = recent if recent is not None else any_remote_activity(args.home, args.my_name)
    now = int(time.time())
    if count > 0:
        print(f"  [ok] collaboration mesh has {count} peer record(s)")
        return 0
    if speakers and recent is not None:
        label = "broadcast peer" if len(speakers) == 1 else "broadcast peers"
        print(
            f"  [ok] collaboration mesh has {len(speakers)} recent {label} "
            f"from signed room traffic (0 direct peer records)"
        )
        print(f"       last remote message {max(0, now - recent.ts)}s ago from {recent.name}")
        return 0
    if recent is not None:
        print(
            f"  [WARN] collaboration mesh has 0 peer records, but remote traffic arrived "
            f"{max(0, now - recent.ts)}s ago from {recent.name}"
        )
        print("         Peer metadata is degraded (DMs/whois may fail), but this is NOT a solo island.")
        return 1
    if any_recent is None:
        print("  [info] collaboration mesh has 0 peer records and no remote history — waiting for first peer")
        print("         Share the invite or ask another agent to join this room; first-user startup is OK.")
        return 0
    print(
        f"  [BLOCKED] collaboration mesh has 0 peer records — last remote traffic was "
        f"{max(0, now - any_recent.ts)}s ago from {any_recent.name}; this may be a solo island"
    )
    print("         Check: airc peers; ask peers to run 'airc update --channel canary && airc join <current invite>'")
    return 2


def cmd_send_warning(args: argparse.Namespace) -> int:
    if peer_record_count(args.home) > 0:
        return 0
    if not recent_remote_speakers(args.home, args.my_name):
        print(
            "  WARN: collaboration has no direct peer records or recent broadcast peers. "
            "Run 'airc peers' and verify others joined this gist.",
            file=sys.stderr,
        )
    return 0


def cmd_peers_fallback(args: argparse.Namespace) -> int:
    speakers = recent_remote_speakers(args.home, args.my_name)
    if not speakers:
        return 1
    print("  Recent broadcast peers:")
    for who, ts in sorted(speakers.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {who} → broadcast room   [(from signed messages.jsonl)]   last seen {_fmt_age(ts)}")
    return 0


def cmd_whois_fallback(args: argparse.Namespace) -> int:
    speakers = recent_remote_speakers(args.home, args.my_name)
    ts = speakers.get(args.peer_name)
    if ts is None:
        return 1
    print(f"  name:      {args.peer_name}")
    print("  pronouns:  (unknown)")
    print("  role:      broadcast peer")
    print("  bio:       seen in recent signed room traffic")
    print("  status:    (unknown)")
    print("  integrations: (none)")
    print(f"  presence:  broadcast-only, last seen {_fmt_age(ts)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.collaboration")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "doctor", "send-warning", "peers-fallback"):
        p = sub.add_parser(name)
        p.add_argument("--home", required=True)
        p.add_argument("--my-name", default="")
    p = sub.add_parser("whois-fallback")
    p.add_argument("--home", required=True)
    p.add_argument("--my-name", default="")
    p.add_argument("--peer-name", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "send-warning":
        return cmd_send_warning(args)
    if args.cmd == "peers-fallback":
        return cmd_peers_fallback(args)
    if args.cmd == "whois-fallback":
        return cmd_whois_fallback(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
