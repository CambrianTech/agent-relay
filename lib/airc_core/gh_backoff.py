"""Shared GitHub API backoff state for AIRC transports."""

from __future__ import annotations

import os
import re
import tempfile
import time


def _uid() -> str:
    return str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")


def backoff_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"airc-gh-backoff-until-{_uid()}")


def backoff_until() -> float:
    try:
        with open(backoff_path(), encoding="utf-8") as f:
            return float(f.read().strip() or "0")
    except (OSError, ValueError):
        return 0.0


def backoff_active() -> bool:
    return time.time() < backoff_until()


def record_backoff(output: str) -> None:
    """Record a shared GitHub backoff window from headers/body."""
    body = (output or "").lower()
    if not body:
        return
    now = time.time()
    until = 0.0
    retry = re.search(r"^retry-after:\s*(\d+)\s*$", body, re.MULTILINE)
    if retry:
        until = now + max(1, int(retry.group(1)))
    else:
        remaining = re.search(r"^x-ratelimit-remaining:\s*(\d+)\s*$", body, re.MULTILINE)
        reset = re.search(r"^x-ratelimit-reset:\s*(\d+)\s*$", body, re.MULTILINE)
        if remaining and reset and remaining.group(1) == "0":
            until = float(reset.group(1))
        elif (
            "secondary rate limit" in body
            or "rate limit exceeded" in body
            or "abuse detection" in body
        ):
            until = now + 60.0
    if until <= now:
        return
    path = backoff_path()
    until = max(until, backoff_until())
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(int(until)))
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def split_include_output(raw: str) -> tuple[str, str]:
    """Return (headers, body) from `gh api --include` output."""
    text = raw or ""
    normalized = text.replace("\r\n", "\n")
    if normalized.startswith("HTTP/") and "\n\n" in normalized:
        headers, body = normalized.split("\n\n", 1)
        return headers, body
    return "", text
