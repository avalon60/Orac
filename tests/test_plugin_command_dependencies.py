"""Tests for safe manifest-declared command prerequisites."""

# Author: Clive Bostock
# Date: 24-Jul-2026
# Description: Verifies strict declarations, fresh probes, and bounded reports.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_command_dependencies import (  # noqa: E402
    PluginCommandDependencyChecker,
)
from model.plugin_command_dependencies import (  # noqa: E402
    PluginCommandDependencyError,
)
from model.plugin_command_dependencies import (  # noqa: E402
    normalise_command_dependencies,
)


def _declaration(*, required: bool = False, specifier: str = ">=3.1,<4"):
    return {
        "command": "pandoc",
        "version_specifier": specifier,
        "required": required,
        "purpose": "Convert documents.",
        "install_hint": "Install Pandoc.",
    }


class PluginCommandDependencyTests(unittest.TestCase):
    """Tests Core-owned validation and command probes."""

    def test_strict_declaration_rejects_unknown_fields_and_duplicates(self) -> None:
        unsafe = {**_declaration(), "arguments": ["--version"]}
        with self.assertRaisesRegex(PluginCommandDependencyError, "unknown field"):
            normalise_command_dependencies([unsafe])
        with self.assertRaisesRegex(PluginCommandDependencyError, "duplicate"):
            normalise_command_dependencies([_declaration(), _declaration()])

    def test_optional_missing_is_degraded_and_required_missing_is_failed(self) -> None:
        optional = normalise_command_dependencies([_declaration()])
        required = normalise_command_dependencies([_declaration(required=True)])
        checker = PluginCommandDependencyChecker(command_path="/tmp/orac-no-commands")

        self.assertEqual(checker.check(optional, context="test").status, "degraded")
        self.assertEqual(checker.check(required, context="test").status, "failed")

    def test_host_pandoc_satisfies_declared_range_without_path_in_report(self) -> None:
        declarations = normalise_command_dependencies([_declaration()])
        result = PluginCommandDependencyChecker().check(
            declarations,
            context="acceptance",
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.probes[0].detected_version, "3.1.3")
        report = result.report_json()
        self.assertLessEqual(len(report.encode("utf-8")), 32 * 1024)
        self.assertNotIn("executable_path", report)
        self.assertEqual(json.loads(report)["probe_context"], "acceptance")


if __name__ == "__main__":
    unittest.main()
