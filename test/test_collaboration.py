"""collaboration health tests.

Run: cd test && python3 test_collaboration.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from airc_core import collaboration  # noqa: E402


class CollaborationHealthTests(unittest.TestCase):
    def _scope(self):
        tmp = tempfile.TemporaryDirectory()
        home = Path(tmp.name)
        (home / "peers").mkdir()
        return tmp, home

    def _remote_line(self, sender="remote-agent"):
        return json.dumps({
            "from": sender,
            "to": "all",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": "general",
            "msg": "hello",
        }) + "\n"

    def test_status_solo_without_records_or_remote_traffic(self):
        tmp, home = self._scope()
        with tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = collaboration.main(["status", "--home", str(home), "--my-name", "me"])
            self.assertEqual(rc, 0)
            self.assertIn("collaboration: SOLO", out.getvalue())

    def test_status_degraded_when_recent_remote_traffic_exists(self):
        tmp, home = self._scope()
        with tmp:
            (home / "messages.jsonl").write_text(self._remote_line(), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = collaboration.main(["status", "--home", str(home), "--my-name", "me"])
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("collaboration: DEGRADED", text)
            self.assertNotIn("collaboration: SOLO", text)

    def test_doctor_warns_not_blocks_when_remote_traffic_exists(self):
        tmp, home = self._scope()
        with tmp:
            (home / "messages.jsonl").write_text(self._remote_line(), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = collaboration.main(["doctor", "--home", str(home), "--my-name", "me"])
            self.assertEqual(rc, 1)
            self.assertIn("remote traffic arrived", out.getvalue())

    def test_send_warning_says_not_solo_when_remote_traffic_exists(self):
        tmp, home = self._scope()
        with tmp:
            (home / "messages.jsonl").write_text(self._remote_line(), encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                rc = collaboration.main(["send-warning", "--home", str(home), "--my-name", "me"])
            self.assertEqual(rc, 0)
            self.assertIn("bus is not solo", err.getvalue())

    def test_peers_fallback_lists_recent_broadcast_speaker(self):
        tmp, home = self._scope()
        with tmp:
            os.rmdir(home / "peers")
            (home / "messages.jsonl").write_text(self._remote_line(), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = collaboration.main(["peers-fallback", "--home", str(home), "--my-name", "me"])
            self.assertEqual(rc, 0)
            self.assertIn("remote-agent", out.getvalue())


if __name__ == "__main__":
    unittest.main()
