"""Idempotent appends for airc messages.jsonl."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

LOCK_STALE_SEC = 30.0
LOCK_WAIT_SEC = 5.0
LOCK_SLEEP_SEC = 0.05
TAIL_LIMIT = 5000


def _line_sig(line: str) -> str:
    try:
        obj = json.loads(line)
    except Exception:
        return ""
    sig = obj.get("sig")
    return sig if isinstance(sig, str) else ""


def _recent_sigs(path: str, limit: int = TAIL_LIMIT) -> set[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-limit:]
    except (FileNotFoundError, OSError):
        return set()
    sigs: set[str] = set()
    for raw in lines:
        sig = _line_sig(raw)
        if sig:
            sigs.add(sig)
    return sigs


def _acquire_lock(path: str) -> str:
    lock_path = f"{path}.lock"
    deadline = time.time() + LOCK_WAIT_SEC
    payload = f"{os.getpid()}\n".encode("ascii", errors="replace")
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
            return lock_path
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(lock_path)
                if age > LOCK_STALE_SEC:
                    os.unlink(lock_path)
                    continue
            except FileNotFoundError:
                continue
            except OSError:
                pass
            if time.time() >= deadline:
                raise TimeoutError(f"timed out waiting for log lock: {lock_path}")
            time.sleep(LOCK_SLEEP_SEC)


def append_unique_sig(path: str, line: str) -> str:
    """Append `line`, skipping if its JSON sig already exists in the log tail."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    framed = line if line.endswith("\n") else line + "\n"
    sig = _line_sig(framed)
    lock_path = _acquire_lock(path)
    try:
        if sig and sig in _recent_sigs(path):
            return "skipped"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, framed.encode("utf-8"))
        finally:
            os.close(fd)
        return "appended"
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def cmd_append(args) -> int:
    line = sys.stdin.read()
    if not line:
        return 0
    try:
        print(append_unique_sig(args.path, line))
    except Exception as e:
        print(f"airc-log-append: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.log_append")
    sub = parser.add_subparsers(dest="cmd", required=True)
    append = sub.add_parser("append")
    append.add_argument("--path", required=True)
    append.set_defaults(func=cmd_append)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
