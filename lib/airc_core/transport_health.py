"""Local transport health checks for AIRC scopes."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChannelHealth:
    channel: str
    ok: bool
    age: int | None
    detail: str


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _safe_gist(gist: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in gist)


def _read_pid(path: Path) -> int:
    try:
        raw = path.read_text(encoding="utf-8").strip().split("\t", 1)[0]
        return int(raw) if raw else 0
    except Exception:
        return 0


def _signal_for_gist(home: Path, channel: str, gist: str, subs: list[str], gists: dict[str, str], own_state: dict) -> tuple[float, str] | None:
    candidates = [(channel, own_state)]
    if gist:
        for other in subs:
            if other == channel or gists.get(other) != gist:
                continue
            other_state = _load_json(home / f"bearer_state.{other}.json")
            if other_state:
                candidates.append((other, other_state))

    best: tuple[float, str] | None = None
    for source, state in candidates:
        ts = state.get("last_heartbeat_ts")
        if ts is None:
            ts = state.get("last_recv_ts")
        if ts is None:
            continue
        try:
            ts_f = float(ts)
        except Exception:
            continue
        if best is None or ts_f > best[0]:
            best = (ts_f, source)
    return best


def evaluate(home: Path, config: Path, fresh_after: int = 90, now: float | None = None) -> list[ChannelHealth]:
    now = time.time() if now is None else now
    cfg = _load_json(config)
    subs = list(cfg.get("subscribed_channels") or [])
    gists = dict(cfg.get("channel_gists") or {})
    if not subs:
        subs = list(gists.keys())
    rows: list[ChannelHealth] = []
    for channel in subs:
        gist = gists.get(channel, "")
        issues: list[str] = []
        age: int | None = None
        if not gist:
            issues.append("missing channel_gists mapping")

        state_path = home / f"bearer_state.{channel}.json"
        state = _load_json(state_path)
        signal_info = _signal_for_gist(home, channel, gist, subs, gists, state)
        if signal_info is not None:
            signal_ts, _source = signal_info
            try:
                age = int(now - signal_ts)
                if age > fresh_after:
                    issues.append(f"stale heartbeat {age}s")
            except Exception:
                issues.append("invalid heartbeat timestamp")
        elif state:
            try:
                mtime_age = int(now - state_path.stat().st_mtime)
            except OSError:
                mtime_age = None
            if mtime_age is not None and mtime_age <= fresh_after:
                age = mtime_age
                issues.append("starting; no heartbeat yet")
            else:
                issues.append("no heartbeat evidence")
        else:
            issues.append("no bearer_state file")

        pid_path = home / f"bearer_gist.{_safe_gist(gist)}.pid" if gist else home / f"bearer_state.{channel}.pid"
        pid = _read_pid(pid_path)
        if not pid:
            issues.append("no bearer pidfile")
        elif not _pid_alive(pid):
            issues.append(f"stale bearer pid {pid}")

        rows.append(ChannelHealth(channel=channel, ok=not issues, age=age, detail="; ".join(issues) if issues else "fresh heartbeat"))
    return rows


def cmd_check(args: argparse.Namespace) -> int:
    rows = evaluate(Path(args.home), Path(args.config), fresh_after=args.fresh_after)
    if not rows:
        return 1
    bad = [row for row in rows if not row.ok]
    if args.quiet:
        return 1 if bad else 0
    if bad:
        print(f"transport health: DEGRADED ({len(bad)}/{len(rows)} channel(s) need attention)")
    else:
        print(f"transport health: ok ({len(rows)} channel(s) fresh)")
    for row in rows:
        suffix = f"{row.age}s" if row.age is not None else "no-signal"
        print(f"#{row.channel}: {'ok' if row.ok else 'DEGRADED'} ({suffix}) — {row.detail}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.transport_health")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("--home", required=True)
    check.add_argument("--config", required=True)
    check.add_argument("--fresh-after", type=int, default=90)
    check.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
