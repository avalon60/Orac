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


    def test_real_poppler_preserves_page_markers_and_rejects_missing_text(self) -> None:
        """Text PDFs retain page provenance; a blank page blocks handoff."""
        declarations = normalise_command_dependencies([{
            "command": "pdftotext", "version_specifier": ">=22,<30",
            "required": False, "purpose": "Extract PDF text.",
            "install_hint": "Install Poppler.",
        }])
        probe = PluginCommandDependencyChecker().check(
            declarations, context="integration"
        ).probes[0]
        if not probe.available:
            self.skipTest("Poppler is not available in the controlled test PATH.")
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.pdf"
            for pages, expected in (
                (("First page", "Second page"), None),
                (("First page", ""), "PDF_TEXT_INCOMPLETE"),
            ):
                with self.subTest(pages=pages):
                    _write_simple_pdf(source, pages)
                    payload = source.read_bytes()
                    kwargs = dict(
                        expected_sha256=hashlib.sha256(payload).hexdigest(),
                        expected_size=len(payload), command_probe=probe,
                        drop_location_id=1, drop_job_id=2,
                    )
                    if expected:
                        with self.assertRaises(DropBoxConversionError) as raised:
                            DropBoxDocumentConverter().normalise(source, **kwargs)
                        self.assertEqual(raised.exception.reason_code, expected)
                    else:
                        result = DropBoxDocumentConverter().normalise(source, **kwargs)
                        self.assertIn("<!-- Page 1 -->\n\nFirst page", result.markdown)
                        self.assertIn("<!-- Page 2 -->\n\nSecond page", result.markdown)
                        self.assertEqual(result.extractor_code, "dropbox_poppler_text")
                        self.assertEqual(source.read_bytes(), payload)


def _write_simple_pdf(path: Path, pages: tuple[str, ...]) -> None:
    """Write a small, valid text PDF fixture without external dependencies."""
    objects: list[bytes | None] = [
        b"<< /Type /Catalog /Pages 2 0 R >>", None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for page in pages:
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        stream = f"BT /F1 12 Tf 72 720 Td ({page}) Tj ET".encode("ascii")
        objects.append((
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>"
        ).encode("ascii"))
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream + b"\nendstream"
        )
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    ).encode("ascii")
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    start_xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend((
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{start_xref}\n%%EOF\n"
    ).encode("ascii"))
    path.write_bytes(data)


if __name__ == "__main__":
    unittest.main()
