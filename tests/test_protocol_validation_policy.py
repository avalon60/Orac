"""Tests for protocol validator fallback policy.

# Author: Clive Bostock
# Date: 2026-05-24
# Description: Verifies that protocol validation fails closed unless an
#   explicit development override is configured.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from lib.protocol_validation import ALLOW_NOOP_PROTOCOL_VALIDATION_ENV
from lib.protocol_validation import disabled_protocol_validator


class ProtocolValidationPolicyTests(unittest.TestCase):
    """Tests fail-closed handling for missing protocol validators."""

    def test_missing_protocol_validator_fails_closed_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Protocol validation is unavailable"):
                disabled_protocol_validator(RuntimeError("missing validator"))

    def test_missing_protocol_validator_allows_explicit_development_noop(self) -> None:
        with patch.dict("os.environ", {ALLOW_NOOP_PROTOCOL_VALIDATION_ENV: "true"}):
            validate_frame, protocol_version = disabled_protocol_validator(
                RuntimeError("missing validator")
            )

        validate_frame({"not": "validated"})
        self.assertEqual(protocol_version, "unknown")


if __name__ == "__main__":
    unittest.main()
