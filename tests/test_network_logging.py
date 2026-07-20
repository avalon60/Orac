"""Tests for content-safe Orac TCP frame logging."""

# Author: Clive Bostock
# Date: 19-Jul-2026
# Description: Verifies protocol log summaries exclude dialogue and authentication data.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.network import _frame_log_summary


class NetworkLoggingTests(unittest.TestCase):
    """Tests non-content metadata emitted for TCP protocol frames."""

    def test_frame_summary_excludes_payload_and_authentication(self) -> None:
        frame = json.dumps(
            {
                "type": "request",
                "id": "req_safe",
                "route": "orac.prompt",
                "meta": {"auth": {"sig": "secret-signature"}},
                "payload": {"messages": [{"content": "private dialogue"}]},
            }
        )

        summary = _frame_log_summary(frame)

        self.assertIn("type=request", summary)
        self.assertIn("route=orac.prompt", summary)
        self.assertIn("id=req_safe", summary)
        self.assertNotIn("private dialogue", summary)
        self.assertNotIn("secret-signature", summary)

    def test_invalid_frame_summary_reports_only_size(self) -> None:
        summary = _frame_log_summary("private invalid dialogue")

        self.assertEqual(summary, "invalid_json bytes=24")


if __name__ == "__main__":
    unittest.main()
