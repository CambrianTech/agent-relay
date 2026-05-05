"""Codex detached-start adapter tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from airc_core import codex_start  # noqa: E402


class CodexStartTests(unittest.TestCase):
    def test_launches_join_in_new_session_with_forced_airc_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "scope"
            log = home / "codex-airc.log"
            calls = []

            class FakePopen:
                def __init__(self, argv, **kwargs):
                    self.pid = 12345
                    calls.append((argv, kwargs))

            with patch("subprocess.Popen", FakePopen), redirect_stdout(StringIO()):
                rc = codex_start.main(
                    [
                        "--airc",
                        "/usr/local/bin/airc",
                        "--home",
                        str(home),
                        "--log",
                        str(log),
                        "--",
                        "--room",
                        "general",
                    ]
                )

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            argv, kwargs = calls[0]
            self.assertEqual(argv, ["/usr/local/bin/airc", "join", "--room", "general"])
            self.assertEqual(kwargs["env"]["AIRC_HOME"], str(home.resolve()))
            self.assertTrue(kwargs["start_new_session"])
            self.assertTrue(kwargs["close_fds"])
            self.assertEqual(kwargs["stderr"], codex_start.subprocess.STDOUT)
            self.assertTrue(home.exists())
            self.assertTrue(log.exists())


if __name__ == "__main__":
    unittest.main()
