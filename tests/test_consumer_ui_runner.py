"""Run the consumer web UI Node smoke test from unittest discovery."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class TestConsumerWebUi(unittest.TestCase):
    def test_consumer_node_smoke_test(self):
        result = subprocess.run(
            ["node", str(ROOT / "tests" / "test_consumer_ui.js")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    sys.exit(unittest.main())
