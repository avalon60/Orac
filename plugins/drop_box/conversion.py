"""Convert supported Drop Box documents to canonical Markdown."""

# Author: Clive Bostock
# Date: 24-Jul-2026
# Description: Owns Drop Box format validation, native normalisation, and Pandoc use.

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import subprocess
import tempfile
import time
import zipfile

from model.plugin_command_dependencies import DEFAULT_COMMAND_PATH
from model.plugin_command_dependencies import PluginCommandProbe

MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_NORMALISED_BYTES = 50 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_EXPANDED_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_RATIO = 200
MAX_TEMP_DIRECTORY_BYTES = 400 * 1024 * 1024
PANDOC_TIMEOUT_SECONDS = 60
OUTPUT_MIME_TYPE = "text/markdown; charset=utf-8"
_HTML_MARKER = re.compile(
    rb"^\s*(?:\xef\xbb\xbf)?(?:<!doctype\s+html\b|<html\b|<!--.*?-->\s*<(?:html|head|body)\b)",
    re.IGNORECASE | re.DOTALL,
)


class DropBoxConversionError(RuntimeError):
    """Raised when a source cannot safely produce canonical Markdown."""

    def __init__(self, reason_code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.reason_code = reason_code
        self.retryable = retryable


@dataclass(frozen=True)
class FormatRecipe:
    """Describe one allowlisted Drop Box input format."""

    source_format_code: str
    mime_type: str
    reader: str | None
    extractor_code: str


@dataclass(frozen=True)
class NormalisedDocument:
    """Canonical Markdown and bounded extraction provenance for Core."""

    markdown: str
    text_sha256: str
    byte_size: int
    source_format_code: str
    source_mime_type: str
    output_mime_type: str
    extractor_code: str
    extractor_version: str
    metadata_json: str


FORMAT_RECIPES = {
    ".md": FormatRecipe(
        "markdown", "text/markdown", None, "dropbox_markdown_passthrough"
    ),
    ".txt": FormatRecipe(
        "plain_text", "text/plain", None, "dropbox_text_to_markdown"
    ),
    ".pdf": FormatRecipe(
        "pdf", "application/pdf", None, "dropbox_poppler_text"
    ),
    ".docx": FormatRecipe(
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
        "dropbox_pandoc_gfm",
    ),
    ".html": FormatRecipe("html", "text/html", "html", "dropbox_pandoc_gfm"),
    ".htm": FormatRecipe("html", "text/html", "html", "dropbox_pandoc_gfm"),
    ".odt": FormatRecipe(
        "odt",
        "application/vnd.oasis.opendocument.text",
        "odt",
        "dropbox_pandoc_gfm",
    ),
    ".rtf": FormatRecipe(
        "rtf", "application/rtf", "rtf", "dropbox_pandoc_gfm"
    ),
    ".epub": FormatRecipe(
        "epub", "application/epub+zip", "epub", "dropbox_pandoc_gfm"
    ),
}


class DropBoxDocumentConverter:
    """Validate and convert one stable source document."""

    def normalise(
        self,
        source_path: Path,
        *,
        expected_sha256: str,
        expected_size: int,
        command_probe: PluginCommandProbe | None = None,
        drop_location_id: int,
        drop_job_id: int,
    ) -> NormalisedDocument:
        """Return canonical Markdown for a verified source."""
        source_path = Path(source_path)
        recipe = FORMAT_RECIPES.get(source_path.suffix.lower())
        if recipe is None:
            raise DropBoxConversionError(
                "UNSUPPORTED_FORMAT", "Drop Box source format is not supported."
            )
        if expected_size < 0 or expected_size > MAX_SOURCE_BYTES:
            raise DropBoxConversionError(
                "SOURCE_TOO_LARGE", "Drop Box source exceeds the 100 MiB limit."
            )
        with tempfile.TemporaryDirectory(prefix="orac-dropbox-convert-") as temp_name:
            root = Path(temp_name)
            staged = root / f"source{source_path.suffix.lower()}"
            digest = _copy_and_hash(source_path, staged)
            if staged.stat().st_size != expected_size or digest != expected_sha256.lower():
                raise DropBoxConversionError(
                    "SOURCE_CHANGED", "Drop Box source changed before conversion."
                )
            self._validate_format(staged, recipe)
            converter_version: str | None = None
            option_ids: list[str] = []
            if recipe.source_format_code == "pdf":
                if command_probe is None or not command_probe.available:
                    raise DropBoxConversionError(
                        "PDFTOTEXT_UNAVAILABLE",
                        "Poppler pdftotext is unavailable in the Drop Box runtime.",
                        retryable=True,
                    )
                converter_version = command_probe.detected_version
                output, option_ids = self._run_pdftotext(staged, command_probe, root)
            elif recipe.reader is None:
                output = canonicalise_utf8(staged.read_bytes())
            else:
                if command_probe is None or not command_probe.available:
                    result_codes = {
                        "missing": "PANDOC_MISSING",
                        "incompatible": "PANDOC_INCOMPATIBLE",
                        "probe_failed": "PANDOC_PROBE_FAILED",
                        "probe_timed_out": "PANDOC_PROBE_TIMED_OUT",
                    }
                    code = result_codes.get(
                        command_probe.result if command_probe else "missing",
                        "PANDOC_PROBE_FAILED",
                    )
                    raise DropBoxConversionError(
                        code,
                        command_probe.reason
                        if command_probe
                        else "Pandoc is unavailable in the Drop Box runtime.",
                        retryable=True,
                    )
                converter_version = command_probe.detected_version
                output, option_ids = self._run_pandoc(
                    staged, recipe, command_probe, root
                )
            encoded = output.encode("utf-8")
            if len(encoded) > MAX_NORMALISED_BYTES:
                raise DropBoxConversionError(
                    "NORMALISED_TOO_LARGE",
                    "Normalised Markdown exceeds the 50 MiB limit.",
                )
            metadata = {
                "schema_version": 1,
                "producer_plugin_id": "drop_box",
                "drop_location_id": int(drop_location_id),
                "drop_job_id": int(drop_job_id),
                "source_format": recipe.source_format_code,
                "converter_name": (
                    "pdftotext" if recipe.source_format_code == "pdf"
                    else "pandoc" if recipe.reader else None
                ),
                "converter_version": converter_version,
                "fixed_option_identifiers": option_ids,
            }
            metadata_json = json.dumps(
                metadata, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            )
            return NormalisedDocument(
                markdown=output,
                text_sha256=hashlib.sha256(encoded).hexdigest(),
                byte_size=len(encoded),
                source_format_code=recipe.source_format_code,
                source_mime_type=recipe.mime_type,
                output_mime_type=OUTPUT_MIME_TYPE,
                extractor_code=recipe.extractor_code,
                extractor_version="1",
                metadata_json=metadata_json,
            )

    def _validate_format(self, path: Path, recipe: FormatRecipe) -> None:
        if recipe.source_format_code == "pdf":
            with path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise DropBoxConversionError(
                        "FORMAT_MISMATCH", "PDF suffix and file signature do not agree."
                    )
            return
        if recipe.source_format_code in {"markdown", "plain_text"}:
            canonicalise_utf8(path.read_bytes())
            return
        if recipe.source_format_code in {"docx", "odt", "epub"}:
            _validate_archive(path, recipe.source_format_code)
            return
        prefix = path.read_bytes()[: 64 * 1024]
        if recipe.source_format_code == "rtf" and not prefix.lstrip().startswith(b"{\\rtf"):
            raise DropBoxConversionError(
                "FORMAT_MISMATCH", "RTF suffix and file signature do not agree."
            )
        if recipe.source_format_code == "html":
            canonicalise_utf8(path.read_bytes())
            if not _HTML_MARKER.search(prefix):
                raise DropBoxConversionError(
                    "FORMAT_MISMATCH",
                    "HTML suffix and content signature do not agree.",
                )

    def _run_pandoc(
        self,
        staged: Path,
        recipe: FormatRecipe,
        probe: PluginCommandProbe,
        root: Path,
    ) -> tuple[str, list[str]]:
        executable = probe.executable_path
        if not executable:
            raise DropBoxConversionError(
                "PANDOC_MISSING", "Pandoc executable was not resolved.", retryable=True
            )
        home = root / "home"
        work = root / "work"
        resources = root / "resources"
        for directory in (home, work, resources):
            directory.mkdir(mode=0o700)
        command = [
            executable,
            "--sandbox",
            f"--from={recipe.reader}",
            "--to=gfm-raw_html",
            "--wrap=none",
            f"--resource-path={resources}",
            str(staged),
        ]
        environment = {
            "PATH": DEFAULT_COMMAND_PATH,
            "HOME": str(home),
            "TMPDIR": str(work),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        process = subprocess.Popen(
            command,
            cwd=work,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )
        stdout, stderr = _communicate_bounded(process, root)
        if process.returncode != 0:
            detail = _bounded_diagnostic(stderr[:MAX_STDERR_BYTES])
            raise DropBoxConversionError(
                "PANDOC_FAILED",
                "Pandoc conversion failed" + (f": {detail}" if detail else "."),
                retryable=True,
            )
        try:
            output = canonicalise_utf8(stdout)
        except DropBoxConversionError as exc:
            raise DropBoxConversionError(
                "INVALID_NORMALISED_OUTPUT", str(exc)
            ) from exc
        return output, [
            "pandoc_sandbox",
            f"reader_{recipe.reader}",
            "writer_gfm_no_raw_html",
            "wrap_none",
            "empty_resource_path",
        ]


    def _run_pdftotext(
        self, staged: Path, probe: PluginCommandProbe, root: Path
    ) -> tuple[str, list[str]]:
        """Extract page-labelled text from a verified text PDF."""
        if not probe.executable_path:
            raise DropBoxConversionError(
                "PDFTOTEXT_UNAVAILABLE", "Poppler executable was not resolved.",
                retryable=True,
            )
        work = root / "work"
        home = root / "home"
        work.mkdir(mode=0o700)
        home.mkdir(mode=0o700)
        process = subprocess.Popen(
            [
                probe.executable_path, "-layout", "-enc", "UTF-8",
                "-eol", "unix", str(staged), "-",
            ],
            cwd=work,
            env={"PATH": DEFAULT_COMMAND_PATH, "HOME": str(home),
                 "TMPDIR": str(work), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )
        stdout, _stderr = _communicate_bounded(process, root, converter_code="PDFTOTEXT")
        if process.returncode != 0:
            raise DropBoxConversionError(
                "PDF_UNREADABLE", "PDF text extraction failed or the file is encrypted."
            )
        try:
            extracted = stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DropBoxConversionError(
                "INVALID_NORMALISED_OUTPUT", "PDF text extraction was not UTF-8."
            ) from exc
        pages = extracted.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        if not pages or any(not page.strip() for page in pages):
            raise DropBoxConversionError(
                "PDF_TEXT_INCOMPLETE", "One or more PDF pages have no extractable text."
            )
        output = "\n\n".join(
            f"<!-- Page {number} -->\n\n{page.strip()}"
            for number, page in enumerate(pages, start=1)
        )
        return canonicalise_utf8(output.encode("utf-8")), [
            "poppler_layout", "utf8", "unix_eol", "page_markers"
        ]


def canonicalise_utf8(payload: bytes) -> str:
    """Apply the version-one native canonicalisation recipe."""
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    if b"\x00" in payload:
        raise DropBoxConversionError(
            "INVALID_UTF8", "Source text contains a NUL byte."
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DropBoxConversionError(
            "INVALID_UTF8", "Source text is not valid UTF-8."
        ) from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise DropBoxConversionError(
            "EMPTY_NORMALISED_OUTPUT", "Normalised Markdown is empty."
        )
    if not text.endswith("\n"):
        text += "\n"
    return text


def _validate_archive(path: Path, source_format: str) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise DropBoxConversionError(
            "FORMAT_MISMATCH", "Document archive is invalid."
        ) from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise DropBoxConversionError(
                "ARCHIVE_LIMIT", "Document archive has too many entries."
            )
        expanded = 0
        names = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts:
                raise DropBoxConversionError(
                    "ARCHIVE_UNSAFE_PATH", "Document archive contains an unsafe path."
                )
            if entry.flag_bits & 0x1:
                raise DropBoxConversionError(
                    "ARCHIVE_ENCRYPTED", "Encrypted document archives are unsupported."
                )
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise DropBoxConversionError(
                    "ARCHIVE_UNSAFE_PATH", "Document archive contains a symbolic link."
                )
            if entry.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise DropBoxConversionError(
                    "ARCHIVE_LIMIT", "Document archive member is too large."
                )
            if entry.compress_size and entry.file_size > entry.compress_size * MAX_ARCHIVE_RATIO:
                raise DropBoxConversionError(
                    "ARCHIVE_LIMIT", "Document archive compression ratio is unsafe."
                )
            expanded += entry.file_size
            if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                raise DropBoxConversionError(
                    "ARCHIVE_LIMIT", "Expanded document archive is too large."
                )
            names.add(entry.filename)
        required = {
            "docx": {"[Content_Types].xml", "word/document.xml"},
            "odt": {"mimetype", "content.xml"},
            "epub": {"mimetype", "META-INF/container.xml"},
        }[source_format]
        if not required.issubset(names):
            raise DropBoxConversionError(
                "FORMAT_MISMATCH",
                f"{source_format.upper()} container structure is incomplete.",
            )
        if source_format in {"odt", "epub"}:
            expected = {
                "odt": b"application/vnd.oasis.opendocument.text",
                "epub": b"application/epub+zip",
            }[source_format]
            if archive.read("mimetype").strip() != expected:
                raise DropBoxConversionError(
                    "FORMAT_MISMATCH",
                    f"{source_format.upper()} mimetype does not match its suffix.",
                )


def _copy_and_hash(source: Path, destination: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
            digest.update(chunk)
            output_handle.write(chunk)
    return digest.hexdigest()


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        else:
            process.kill()
        process.wait()


def _communicate_bounded(
    process: subprocess.Popen[bytes],
    temporary_root: Path,
    *,
    converter_code: str = "PANDOC",
) -> tuple[bytes, bytes]:
    """Read converter pipes while enforcing time, output, and temporary limits."""
    if process.stdout is None or process.stderr is None:
        _terminate_process(process)
        raise DropBoxConversionError(
            f"{converter_code}_FAILED", "Converter output pipes were not available.", retryable=True
        )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout = bytearray()
    stderr = bytearray()
    started = time.monotonic()
    next_storage_check = started
    try:
        while selector.get_map():
            now = time.monotonic()
            if now - started > PANDOC_TIMEOUT_SECONDS:
                _terminate_process(process)
                raise DropBoxConversionError(
                    f"{converter_code}_TIMEOUT",
                    "Conversion timed out.",
                    retryable=True,
                )
            if now >= next_storage_check:
                if _directory_size(temporary_root) > MAX_TEMP_DIRECTORY_BYTES:
                    _terminate_process(process)
                    raise DropBoxConversionError(
                        "TEMP_STORAGE_LIMIT",
                        "Converter temporary storage exceeded 400 MiB.",
                    )
                next_storage_check = now + 0.25
            events = selector.select(timeout=0.1)
            for key, _mask in events:
                chunk = os.read(key.fd, 64 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "stdout":
                    stdout.extend(chunk)
                    if len(stdout) > MAX_NORMALISED_BYTES:
                        _terminate_process(process)
                        raise DropBoxConversionError(
                            "NORMALISED_TOO_LARGE",
                            "Converter output exceeds the 50 MiB limit.",
                        )
                elif len(stderr) < MAX_STDERR_BYTES:
                    remaining = MAX_STDERR_BYTES - len(stderr)
                    stderr.extend(chunk[:remaining])
        process.wait(timeout=2)
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return bytes(stdout), bytes(stderr)


def _directory_size(root: Path) -> int:
    """Return the bounded private conversion-directory size."""
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
        if total > MAX_TEMP_DIRECTORY_BYTES:
            break
    return total


def _bounded_diagnostic(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace")
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = re.sub(r"(?:/[A-Za-z0-9._-]+){2,}", "<path>", text)
    return " ".join(text.split())[:512]
