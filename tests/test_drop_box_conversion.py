"""Tests for Drop Box document canonicalisation and format validation."""

# Author: Clive Bostock
# Date: 24-Jul-2026
# Description: Verifies native normalisation and safe format rejection.

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for root in (SRC_ROOT, PLUGINS_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from drop_box.conversion import DropBoxConversionError  # noqa: E402
from drop_box.conversion import DropBoxDocumentConverter  # noqa: E402
from drop_box.conversion import canonicalise_utf8  # noqa: E402
from model.plugin_command_dependencies import (  # noqa: E402
    PluginCommandDependencyChecker,
)
from model.plugin_command_dependencies import (  # noqa: E402
    normalise_command_dependencies,
)


class DropBoxConversionTests(unittest.TestCase):
    """Tests the Drop Box-owned conversion boundary."""

    def test_native_canonicalisation_preserves_utf8_and_normalises_lines(self) -> None:
        cases = (
            (b"\xef\xbb\xbf# Heading\r\nbody\r", "# Heading\nbody\n"),
            ("café 🙂".encode("utf-8"), "café 🙂\n"),
            (b"one\rtwo\r\nthree\n", "one\ntwo\nthree\n"),
            (b"text\n\n", "text\n\n"),
        )
        for payload, expected in cases:
            with self.subTest(payload=payload):
                self.assertEqual(canonicalise_utf8(payload), expected)

    def test_native_rejects_invalid_utf8_nul_and_blank_output(self) -> None:
        for payload in (b"\xff", b"a\x00b", b" \r\n\t"):
            with self.subTest(payload=payload):
                with self.assertRaises(DropBoxConversionError):
                    canonicalise_utf8(payload)

    def test_markdown_normalisation_hashes_exact_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "note.md"
            source.write_bytes(b"# Note\r\n")
            payload = source.read_bytes()
            result = DropBoxDocumentConverter().normalise(
                source,
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                expected_size=len(payload),
                drop_location_id=1,
                drop_job_id=2,
            )

        self.assertEqual(result.markdown, "# Note\n")
        self.assertEqual(
            result.text_sha256,
            hashlib.sha256(b"# Note\n").hexdigest(),
        )
        self.assertEqual(result.extractor_code, "dropbox_markdown_passthrough")

    def test_archive_traversal_is_rejected_before_pandoc(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "unsafe.docx"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("word/document.xml", "<document/>")
                archive.writestr("../secret", "no")
            payload = source.read_bytes()
            with self.assertRaisesRegex(DropBoxConversionError, "unsafe path"):
                DropBoxDocumentConverter().normalise(
                    source,
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                    expected_size=len(payload),
                    drop_location_id=1,
                    drop_job_id=2,
                )

    def test_real_pandoc_acceptance_for_supported_readers(self) -> None:
        declarations = normalise_command_dependencies(
            [
                {
                    "command": "pandoc",
                    "version_specifier": ">=3.1,<4",
                    "required": False,
                    "purpose": "Convert documents.",
                    "install_hint": "Install Pandoc.",
                }
            ]
        )
        probe = PluginCommandDependencyChecker().check(
            declarations,
            context="integration",
        ).probes[0]
        if not probe.available:
            self.skipTest("Pandoc is not available in the controlled test PATH.")

        fixture = PROJECT_ROOT / "tests/fixtures/knowledge/drop_box_fixture.md"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix in (".docx", ".html", ".odt", ".rtf", ".epub"):
                with self.subTest(suffix=suffix):
                    source = root / f"fixture{suffix}"
                    command = [probe.executable_path or "pandoc", str(fixture)]
                    if suffix in {".html", ".rtf"}:
                        command.append("--standalone")
                    command.extend(["--output", str(source)])
                    subprocess.run(command, check=True, timeout=30)
                    payload = source.read_bytes()
                    result = DropBoxDocumentConverter().normalise(
                        source,
                        expected_sha256=hashlib.sha256(payload).hexdigest(),
                        expected_size=len(payload),
                        command_probe=probe,
                        drop_location_id=1,
                        drop_job_id=2,
                    )
                    self.assertTrue(result.markdown.strip())
                    self.assertEqual(result.extractor_code, "dropbox_pandoc_gfm")


if __name__ == "__main__":
    unittest.main()
