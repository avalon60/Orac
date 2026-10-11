"""Safely validate and probe manifest-declared command prerequisites."""

# Author: Clive Bostock
# Date: 24-Jul-2026
# Description: Provides the Core-owned command probe catalogue and bounded reports.

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Iterable, Sequence

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from model.plugin_routing.models import PluginCommandDependency

MAX_COMMAND_DEPENDENCIES = 16
MAX_REPORT_BYTES = 32 * 1024
MAX_PROBE_OUTPUT_BYTES = 64 * 1024
DEFAULT_COMMAND_PATH = "/usr/local/bin:/usr/bin:/bin"
COMMAND_RESULTS = {
    "available",
    "missing",
    "incompatible",
    "probe_failed",
    "probe_timed_out",
}
_COMMAND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PANDOC_VERSION = re.compile(r"^pandoc\s+([0-9]+(?:\.[0-9A-Za-z]+)*)", re.IGNORECASE)
_PDFTOTEXT_VERSION = re.compile(r"^pdftotext version\s+([0-9]+(?:\.[0-9A-Za-z]+)*)", re.IGNORECASE)


class PluginCommandDependencyError(RuntimeError):
    """Raised when a command declaration or probe cannot be handled safely."""


@dataclass(frozen=True)
class PluginCommandProbe:
    """Describe one evaluated command dependency."""

    command: str
    required: bool
    version_specifier: str
    result: str
    detected_version: str | None
    reason_code: str
    reason: str
    executable_path: str | None = None

    @property
    def available(self) -> bool:
        """Return whether the command satisfies its declaration."""
        return self.result == "available"

    def report_value(self) -> dict[str, object]:
        """Return the bounded persistable form without executable paths."""
        return {
            "command": self.command,
            "required": self.required,
            "version_specifier": self.version_specifier,
            "result": self.result,
            "detected_version": self.detected_version,
            "reason_code": self.reason_code,
            "reason": _bounded_text(self.reason, 512),
        }


@dataclass(frozen=True)
class PluginCommandDependencyResult:
    """Describe all command prerequisites for one consuming plugin."""

    status: str
    probes: tuple[PluginCommandProbe, ...]
    context: str

    @property
    def warnings(self) -> tuple[str, ...]:
        """Return operator-facing warnings for unsatisfied optional commands."""
        return tuple(
            probe.reason
            for probe in self.probes
            if not probe.required and not probe.available
        )

    def report_json(self) -> str:
        """Return deterministic bounded JSON suitable for registry storage."""
        value = {
            "schema_version": 1,
            "aggregate_status": self.status,
            "probe_context": self.context,
            "dependencies": [probe.report_value() for probe in self.probes],
        }
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
            raise PluginCommandDependencyError(
                "Command dependency report exceeds the 32 KiB registry limit."
            )
        return encoded


@dataclass(frozen=True)
class _ProbeDefinition:
    arguments: tuple[str, ...]
    version_pattern: re.Pattern[str]
    timeout_seconds: float


SAFE_PROBE_CATALOGUE = {
    "pandoc": _ProbeDefinition(
        arguments=("--version",),
        version_pattern=_PANDOC_VERSION,
        timeout_seconds=5.0,
    ),
    "pdftotext": _ProbeDefinition(
        arguments=("-v",),
        version_pattern=_PDFTOTEXT_VERSION,
        timeout_seconds=5.0,
    ),
}


def normalise_command_dependencies(value: object) -> tuple[PluginCommandDependency, ...]:
    """Validate command dependency manifest data.

    Args:
        value: Manifest value expected to be a list of strict objects.

    Returns:
        Validated declarations in manifest order.

    Raises:
        PluginCommandDependencyError: If any declaration is unsafe or invalid.
    """
    if not isinstance(value, list):
        raise PluginCommandDependencyError("must be a list")
    if len(value) > MAX_COMMAND_DEPENDENCIES:
        raise PluginCommandDependencyError(
            f"must contain at most {MAX_COMMAND_DEPENDENCIES} entries"
        )
    declarations: list[PluginCommandDependency] = []
    seen: set[str] = set()
    allowed = {
        "command",
        "version_specifier",
        "required",
        "purpose",
        "install_hint",
    }
    for index, raw in enumerate(value):
        field = f"entry {index}"
        if not isinstance(raw, dict):
            raise PluginCommandDependencyError(f"{field} must be an object")
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise PluginCommandDependencyError(
                f"{field} has unknown field(s): {', '.join(unknown)}"
            )
        missing = sorted(allowed - set(raw))
        if missing:
            raise PluginCommandDependencyError(
                f"{field} missing field(s): {', '.join(missing)}"
            )
        command = _manifest_text(raw["command"], f"{field}.command", 64)
        if not _COMMAND_PATTERN.fullmatch(command):
            raise PluginCommandDependencyError(
                f"{field}.command must be a lower-case command identifier"
            )
        if command not in SAFE_PROBE_CATALOGUE:
            raise PluginCommandDependencyError(
                f"{field}.command '{command}' is not registered"
            )
        if command in seen:
            raise PluginCommandDependencyError(
                f"duplicate command dependency declaration for '{command}'"
            )
        seen.add(command)
        specifier = _manifest_text(
            raw["version_specifier"], f"{field}.version_specifier", 128
        )
        try:
            SpecifierSet(specifier)
        except InvalidSpecifier as exc:
            raise PluginCommandDependencyError(
                f"{field}.version_specifier is invalid"
            ) from exc
        required = raw["required"]
        if not isinstance(required, bool):
            raise PluginCommandDependencyError(f"{field}.required must be boolean")
        declarations.append(
            PluginCommandDependency(
                command=command,
                version_specifier=specifier,
                required=required,
                purpose=_manifest_text(raw["purpose"], f"{field}.purpose", 500),
                install_hint=_manifest_text(
                    raw["install_hint"], f"{field}.install_hint", 500
                ),
            )
        )
    return tuple(declarations)


def command_dependency_fingerprint(
    declarations: Iterable[PluginCommandDependency],
) -> str:
    """Return a stable SHA-256 fingerprint for command declarations."""
    import hashlib

    values = [
        {
            "command": item.command,
            "version_specifier": item.version_specifier,
            "required": item.required,
            "purpose": item.purpose,
            "install_hint": item.install_hint,
        }
        for item in declarations
    ]
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PluginCommandDependencyChecker:
    """Probe registered commands using fixed catalogue-owned behaviour."""

    def __init__(self, *, command_path: str = DEFAULT_COMMAND_PATH) -> None:
        """Initialise the checker with a controlled executable search path."""
        parts = command_path.split(os.pathsep)
        if not parts or any(not part or not Path(part).is_absolute() for part in parts):
            raise PluginCommandDependencyError(
                "Command PATH must contain only absolute, non-empty directories."
            )
        self._command_path = command_path

    def check(
        self,
        declarations: Sequence[PluginCommandDependency],
        *,
        context: str,
    ) -> PluginCommandDependencyResult:
        """Probe every declaration without reusing a previous success."""
        probes = tuple(self._probe(item) for item in declarations)
        if not probes:
            status = "not_applicable"
        elif any(not probe.available and probe.required for probe in probes):
            status = "failed"
        elif any(not probe.available for probe in probes):
            status = "degraded"
        else:
            status = "success"
        return PluginCommandDependencyResult(
            status=status,
            probes=probes,
            context=_bounded_text(context, 64),
        )

    def _probe(self, declaration: PluginCommandDependency) -> PluginCommandProbe:
        definition = SAFE_PROBE_CATALOGUE[declaration.command]
        executable = shutil.which(declaration.command, path=self._command_path)
        if executable is None:
            return self._result(
                declaration,
                result="missing",
                reason_code="executable_not_found",
                reason=(
                    f"{declaration.command} was not found on the controlled service PATH. "
                    f"{declaration.install_hint}"
                ),
            )
        with tempfile.TemporaryDirectory(prefix="orac-command-probe-") as temp_name:
            temp_root = Path(temp_name)
            home = temp_root / "home"
            work = temp_root / "tmp"
            home.mkdir(mode=0o700)
            work.mkdir(mode=0o700)
            environment = {
                "PATH": self._command_path,
                "HOME": str(home),
                "TMPDIR": str(work),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            try:
                process = subprocess.Popen(
                    [executable, *definition.arguments],
                    cwd=work,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=(os.name == "posix"),
                )
                return_code, stdout, stderr = _read_probe_output(
                    process,
                    timeout_seconds=definition.timeout_seconds,
                )
            except TimeoutError:
                return self._result(
                    declaration,
                    result="probe_timed_out",
                    reason_code="probe_timeout",
                    reason=f"{declaration.command} version probe timed out.",
                )
            except OSError as exc:
                return self._result(
                    declaration,
                    result="probe_failed",
                    reason_code="probe_start_failed",
                    reason=f"{declaration.command} version probe could not start: {exc}",
                )
            except OverflowError:
                return self._result(
                    declaration,
                    result="probe_failed",
                    reason_code="probe_output_limit",
                    reason=f"{declaration.command} version probe exceeded its output limit.",
                )
        if return_code != 0:
            detail = _sanitise_output(stderr or stdout)
            return self._result(
                declaration,
                result="probe_failed",
                reason_code="probe_non_zero",
                reason=(
                    f"{declaration.command} version probe failed"
                    + (f": {detail}" if detail else ".")
                ),
            )
        text = _sanitise_output(stdout or stderr)
        match = definition.version_pattern.search(text)
        if match is None:
            return self._result(
                declaration,
                result="probe_failed",
                reason_code="version_unrecognised",
                reason=f"{declaration.command} returned an unrecognised version.",
            )
        try:
            version = str(Version(match.group(1)))
        except InvalidVersion:
            return self._result(
                declaration,
                result="probe_failed",
                reason_code="version_invalid",
                reason=f"{declaration.command} returned an invalid version.",
            )
        if Version(version) not in SpecifierSet(declaration.version_specifier):
            return self._result(
                declaration,
                result="incompatible",
                detected_version=version,
                reason_code="version_incompatible",
                reason=(
                    f"{declaration.command} {version} does not satisfy "
                    f"{declaration.version_specifier}. {declaration.install_hint}"
                ),
                executable_path=executable,
            )
        return self._result(
            declaration,
            result="available",
            detected_version=version,
            reason_code="available",
            reason=f"{declaration.command} {version} is available.",
            executable_path=executable,
        )

    @staticmethod
    def _result(
        declaration: PluginCommandDependency,
        *,
        result: str,
        reason_code: str,
        reason: str,
        detected_version: str | None = None,
        executable_path: str | None = None,
    ) -> PluginCommandProbe:
        if result not in COMMAND_RESULTS:
            raise PluginCommandDependencyError(f"Unknown probe result: {result}")
        return PluginCommandProbe(
            command=declaration.command,
            required=declaration.required,
            version_specifier=declaration.version_specifier,
            result=result,
            detected_version=detected_version,
            reason_code=reason_code,
            reason=_bounded_text(_sanitise_output(reason.encode("utf-8")), 512),
            executable_path=executable_path,
        )


def _manifest_text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PluginCommandDependencyError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise PluginCommandDependencyError(f"{field} must not be empty")
    if len(cleaned) > maximum:
        raise PluginCommandDependencyError(
            f"{field} must be at most {maximum} characters"
        )
    if _CONTROL_CHARACTER.search(cleaned):
        raise PluginCommandDependencyError(
            f"{field} must not contain control characters"
        )
    return cleaned


def _sanitise_output(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace")
    text = _CONTROL_CHARACTER.sub(" ", text)
    text = re.sub(r"https?://[^@\s]+@", "https://***@", text)
    text = re.sub(r"(?:/[A-Za-z0-9._-]+){2,}", "<path>", text)
    return " ".join(text.split())


def _bounded_text(value: str, maximum: int) -> str:
    return value if len(value) <= maximum else value[: maximum - 1] + "…"


def _read_probe_output(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> tuple[int, bytes, bytes]:
    """Read fixed command-probe output without allowing unbounded capture."""
    if process.stdout is None or process.stderr is None:
        _terminate_probe(process)
        raise OSError("Probe output pipes were not available.")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout = bytearray()
    stderr = bytearray()
    started = time.monotonic()
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout_seconds:
                _terminate_probe(process)
                raise TimeoutError
            for key, _mask in selector.select(timeout=0.05):
                chunk = os.read(key.fd, 16 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = stdout if key.data == "stdout" else stderr
                target.extend(chunk)
                if len(target) > MAX_PROBE_OUTPUT_BYTES:
                    _terminate_probe(process)
                    raise OverflowError
        return process.wait(timeout=1), bytes(stdout), bytes(stderr)
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


def _terminate_probe(process: subprocess.Popen[bytes]) -> None:
    """Terminate the probe process group where the platform supports it."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        else:
            process.kill()
        process.wait()
