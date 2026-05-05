"""System event tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from airc_core import system_event  # noqa: E402


class JoinEventTests(unittest.TestCase):
    def test_join_event_for_each_subscribed_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.json").write_text(
                json.dumps({"subscribed_channels": ["cambriantech", "general"]}),
                encoding="utf-8",
            )

            system_event.append_join(str(home), "airc-8a5e", "agent:test")

            lines = [
                json.loads(line)
                for line in (home / "messages.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([line["channel"] for line in lines], ["cambriantech", "general"])
            self.assertEqual(lines[0]["from"], "airc")
            self.assertEqual(lines[0]["to"], "all")
            self.assertEqual(lines[0]["client_id"], "agent:test")
            self.assertEqual(lines[0]["msg"], "airc-8a5e joined #cambriantech")
            self.assertEqual(lines[1]["msg"], "airc-8a5e joined #general")


if __name__ == "__main__":
    unittest.main()
