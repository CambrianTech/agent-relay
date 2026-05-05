"""Transport health tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from airc_core import transport_health  # noqa: E402


class TransportHealthTests(unittest.TestCase):
    def _scope(self):
        tmp = tempfile.TemporaryDirectory()
        home = Path(tmp.name)
        config = home / "config.json"
        config.write_text(
            json.dumps(
                {
                    "subscribed_channels": ["general"],
                    "channel_gists": {"general": "c68640ec0144b422c16b2d8c83ad5ee5"},
                }
            ),
            encoding="utf-8",
        )
        return tmp, home, config

    def test_fresh_heartbeat_and_live_pid_is_healthy(self):
        tmp, home, config = self._scope()
        with tmp:
            now = time.time()
            (home / "bearer_state.general.json").write_text(json.dumps({"last_heartbeat_ts": now}), encoding="utf-8")
            (home / "bearer_gist.c68640ec0144b422c16b2d8c83ad5ee5.pid").write_text(str(os.getpid()), encoding="utf-8")
            rows = transport_health.evaluate(home, config, now=now)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].ok)

    def test_formatter_without_fresh_bearer_is_degraded(self):
        tmp, home, config = self._scope()
        with tmp:
            now = time.time()
            (home / "bearer_state.general.json").write_text(json.dumps({"last_heartbeat_ts": now - 300}), encoding="utf-8")
            (home / "bearer_gist.c68640ec0144b422c16b2d8c83ad5ee5.pid").write_text("999999", encoding="utf-8")
            rows = transport_health.evaluate(home, config, now=now)
            self.assertFalse(rows[0].ok)
            self.assertIn("stale heartbeat", rows[0].detail)
            self.assertIn("stale bearer pid", rows[0].detail)


if __name__ == "__main__":
    unittest.main()
