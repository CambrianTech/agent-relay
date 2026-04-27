"""ISO 8601 ↔ Unix epoch conversion for airc.

Migrated from the bash `iso_to_epoch` adapter (PR #151) into the Python
truth-layer (PR #152 architecture). The bash adapter handled three
fallback paths (BSD date, GNU date, python3 datetime); now that we
have Python as the canonical layer, we just use stdlib datetime.

The bash side calls into this module via:

    "$AIRC_PYTHON" -m airc_core.datetime iso_to_epoch <ts>

That subprocess call is the new shape — bash never re-implements logic
that lives here.
"""

from __future__ import annotations

import datetime
import sys


def iso_to_epoch(ts: str) -> int | None:
    """Convert an ISO 8601 UTC timestamp to a Unix epoch integer.

    Accepts the canonical airc gist envelope timestamp shape
    `YYYY-MM-DDTHH:MM:SSZ` (e.g. `2026-04-27T03:25:54Z`). Returns None
    on parse failure rather than raising — callers in bash use the
    empty/non-empty distinction to decide whether to skip a stale
    check (matches the pre-migration adapter contract).
    """
    if not ts:
        return None
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _cli() -> int:
    """CLI entry: `python -m airc_core.datetime iso_to_epoch <ts>`.

    Echoes the epoch on success; empty output on failure (exit 0).
    Matches the bash adapter's stdout contract — callers do
    `epoch=$(... iso_to_epoch "$ts")` and check for empty.
    """
    if len(sys.argv) < 2:
        return 2
    cmd = sys.argv[1]
    if cmd == "iso_to_epoch":
        ts = sys.argv[2] if len(sys.argv) > 2 else ""
        result = iso_to_epoch(ts)
        if result is not None:
            print(result)
        return 0
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
