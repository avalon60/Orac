"""Configure Orac logging and provide content-safe call timing helpers."""

# Author: Clive Bostock
# Date: 11-Oct-2026
# Description: Configure process-wide Loguru sinks and TRACE call timing.

from pathlib import Path
import functools
import inspect
import os
import threading
import time
from contextlib import aclosing
from contextvars import ContextVar
from typing import Callable, Any, Optional
from loguru import logger as logr
from sys import stderr

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons

# Disable auto-init; we will configure explicitly.
os.environ["LOGURU_AUTOINIT"] = "0"

APP_HOME = project_home()
DEFAULT_LOGS_DIR = APP_HOME / "logs"
CONFIG_DIR = APP_HOME / "resources" / "config"
CONFIG_FILE = CONFIG_DIR / "orac.ini"
DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

config_manager = ConfigManager(config_file_path=CONFIG_FILE)

# ----------------------------
# Process-global config guards
# ----------------------------
_CONFIG_LOCK = threading.RLock()
_CALL_DEPTH: ContextVar[int] = ContextVar("orac_log_call_depth", default=-1)


class _DepthIterator:
    """Run generator operations at their call depth without leaking it to consumers."""

    def __init__(self, iterator: Any, depth: int) -> None:
        self._iterator = iterator
        self._depth = depth

    def __iter__(self) -> "_DepthIterator":
        return self

    def _invoke(self, method: str, *args: Any) -> Any:
        token = _CALL_DEPTH.set(self._depth)
        try:
            return getattr(self._iterator, method)(*args)
        finally:
            _CALL_DEPTH.reset(token)

    def __next__(self) -> Any:
        return self._invoke("__next__")

    def send(self, value: Any) -> Any:
        return self._invoke("send", value)

    def throw(self, *args: Any) -> Any:
        return self._invoke("throw", *args)

    def close(self) -> Any:
        return self._invoke("close")


class _DepthAsyncIterator:
    """Run asynchronous generator advancement and closure at its call depth."""

    def __init__(self, iterator: Any, depth: int) -> None:
        self._iterator = iterator
        self._depth = depth

    async def __anext__(self) -> Any:
        token = _CALL_DEPTH.set(self._depth)
        try:
            return await self._iterator.__anext__()
        finally:
            _CALL_DEPTH.reset(token)

    async def aclose(self) -> None:
        token = _CALL_DEPTH.set(self._depth)
        try:
            await self._iterator.aclose()
        finally:
            _CALL_DEPTH.reset(token)

def _get_state() -> str:
    """Gets the current logging configuration state.

    Returns:
        str: The current state, e.g., "idle", "configuring", or "configured".
    """
    return getattr(logr, "_ORAC_LOG_STATE", "idle")

def _set_state(state: str) -> None:
    """Sets the current logging configuration state.

    Args:
        state: The new state to set.
    """
    setattr(logr, "_ORAC_LOG_STATE", state)

def _get_file_path() -> Optional[str]:
    """Gets the path to the current log file, if configured.

    Returns:
        Optional[str]: The path of the configured log file, or None.
    """
    return getattr(logr, "_ORAC_LOG_FILE", None)

def _set_file_path(p: Path) -> None:
    """Sets the path to the configured log file.

    Args:
        p: The path object of the log file.
    """
    setattr(logr, "_ORAC_LOG_FILE", str(p))


def _fd_targets_path(fd: int, path: Path) -> bool:
    """Return whether a process file descriptor points at ``path``."""
    try:
        target = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return False

    if not target.startswith("/"):
        return False

    target_path = Path(target.removesuffix(" (deleted)"))
    try:
        return os.path.samefile(target_path, path)
    except OSError:
        return target_path.resolve() == path.resolve()


# -------------
# Run ID helper
# -------------
class RunIDManager:
    """Manages a process-wide, epoch-based Run ID.

    The Run ID is generated once upon the first instantiation of this class
    and is formatted for readability.
    """
    _instance: Optional["RunIDManager"] = None
    _run_id: Optional[int] = None

    def __new__(cls):
        """Ensures a single instance of the manager is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._run_id = int(time.time())
        return cls._instance

    @property
    def run_id(self) -> str:
        """Returns the formatted, process-wide Run ID.

        Returns:
            str: The formatted Run ID (e.g., '25-0919-1630').
        """
        return self.format_epoch_id(str(self._run_id))

    @staticmethod
    def format_epoch_id(epoch_id: str) -> str:
        """Formats a 10-digit epoch timestamp into a readable string.

        Args:
            epoch_id: A 10-digit string representing an epoch timestamp.

        Returns:
            str: The formatted ID string, e.g., '25-0919-1630'.

        Raises:
            ValueError: If the epoch ID is not exactly 10 digits.
        """
        if len(epoch_id) != 10 or not epoch_id.isdigit():
            raise ValueError("Epoch ID must be exactly 10 digits.")
        return f"{epoch_id[:2]}-{epoch_id[2:6]}-{epoch_id[6:]}"


RUN_ID = RunIDManager().run_id


def log_stamp(post_underscore: bool = True, pref_underscore: bool = False) -> str:
    """Generates a millisecond-precision timestamp for log file or context stamping.

    The stamp generation is controlled by a configuration value. If disabled
    in config, an empty string is returned.

    Args:
        post_underscore: If True, adds an underscore *after* the timestamp. Defaults to True.
        pref_underscore: If True, adds an underscore *before* the timestamp. Defaults to False.

    Returns:
        str: The timestamp string (e.g., "1632000000000_") or an empty string.
    """
    log_stamping = config_manager.bool_config_value("logging", "log_stamping", default=False)
    _ls = str(int(round(time.time() * 1000)))
    if post_underscore:
        _ls += "_"
    if pref_underscore:
        _ls = "_" + _ls
    return _ls if log_stamping else ""


# ---------------
# Logger wrapper
# ---------------
class Logger:
    """Process-wide singleton around Loguru configuration.

    This class ensures Loguru is configured only once per process,
    is thread-safe against race conditions, and prevents duplicate sinks
    across multiple imports/initializations.
    """

    _instance: Optional["Logger"] = None
    _file_sink_id: Optional[int] = None
    _stderr_sink_id: Optional[int] = None

    def __new__(cls, *args, **kwargs):
        """Ensures a single instance of the Logger is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get(cls) -> "Logger":
        """Retrieves the singleton Logger instance.

        Returns:
            Logger: The process-wide Logger instance.
        """
        return cls()

    def __init__(self, log_file: Optional[Path] = None, log_level: str = "INFO", inc_std_err: bool = None):
        """Initializes the Logger, attempting configuration if needed.

        Configuration is guarded to run only once per process.

        Args:
            log_file: Optional Path to the desired log file. Defaults to
                'logs/orac.log' within the project home.
            log_level: The minimum logging level (e.g., 'DEBUG', 'INFO'). Defaults to 'INFO'.
            inc_std_err: Optional boolean to explicitly include or exclude the
                stderr sink. Defaults to the value from the configuration file.
        """
        # “Construction” may be called multiple times; configuration is guarded.
        self.log_file = log_file or (DEFAULT_LOGS_DIR / "orac.log")
        self.log_level = (log_level or "INFO").upper()
        self.include_stderr = (
            inc_std_err if inc_std_err is not None
            else config_manager.bool_config_value("logging", "inc_stderr", default=True)
        )
        self._ensure_configured()

    def _fmt(self) -> str:
        """Generates the log message format string for Loguru.

        Returns:
            str: The format string including timestamp, process ID, level, and message.
        """
        # Include {process} to help spot cross-process writers.
        return (
            "<green>{time:DD/MM/YYYY HH:mm:ss}</green> | {process} | "
            "<level>{level:<8}</level> | <level>{message}</level>"
        )

    def _ensure_configured(self) -> None:
        """Performs the thread-safe, process-wide configuration of Loguru sinks.

        This method is guaranteed to run configuration only once per process.
        It adds the file sink and the optional stderr sink.
        """
        # Fast-path: if already configured for this same file, bail.
        if _get_state() == "configured" and _get_file_path() == str(self.log_file):
            return

        with _CONFIG_LOCK:
            # Re-check inside the lock (prevents races).
            if _get_state() == "configured" and _get_file_path() == str(self.log_file):
                return
            if _get_state() == "configuring":
                # Another thread is configuring; nothing to do.
                return

            _set_state("configuring")

            try:
                # Clean slate once per process.
                logr.remove()

                # Ensure directory exists.
                self.log_file.parent.mkdir(parents=True, exist_ok=True)

                # File sink first.
                Logger._file_sink_id = logr.add(
                    sink=self.log_file,
                    level=self.log_level,
                    format=self._fmt(),
                )
                _set_file_path(self.log_file)
                _set_state("configured")  # important: flip early to block late joiners

                logr.info(f"{Icons.tick} Logging initialized at {self.log_file}")

                # Optional stderr sink. If the process was launched with
                # stderr redirected to the same log file, adding both sinks
                # duplicates every line.
                include_stderr = self.include_stderr and not _fd_targets_path(
                    2,
                    self.log_file,
                )
                if include_stderr:
                    Logger._stderr_sink_id = logr.add(
                        sink=stderr,
                        level=self.log_level,
                        format=self._fmt(),
                    )
                    logr.debug(f"{Icons.info} Console logging ENABLED (stderr sink active)")
                else:
                    logr.debug(f"{Icons.warn} Console logging DISABLED (stderr sink skipped)")

            except Exception:
                # Don’t leave state stuck.
                _set_state("idle")
                raise

    # Convenience wrappers
    def log_info(self, message: str) -> None:
        """Logs an INFO level message using the configured logger.

        Args:
            message: The message string to log.
        """
        logr.info(f"{Icons.info} {message}")

    def log_debug(self, message: str) -> None:
        """Logs a DEBUG level message using the configured logger.

        Args:
            message: The message string to log.
        """
        logr.debug(f"{Icons.idea} {message}")

    def log_warning(self, message: str) -> None:
        """Logs a WARNING level message using the configured logger.

        Args:
            message: The message string to log.
        """
        logr.warning(f"{Icons.warn} {message}")

    def log_error(self, message: str) -> None:
        """Logs an ERROR level message using the configured logger.

        Args:
            message: The message string to log.
        """
        logr.error(f"{Icons.error} {message}")

    def log_critical(self, message: str) -> None:
        """Logs a CRITICAL level message using the configured logger.

        Args:
            message: The message string to log.
        """
        logr.critical(f"{Icons.critical} {message}")

    # Change level without multiplying sinks
    def set_level(self, level: str) -> None:
        """Changes the logging level dynamically for all active sinks.

        The existing sinks are removed and immediately re-added with the new level.

        Args:
            level: The new minimum logging level (e.g., 'DEBUG', 'ERROR').
        """
        self.log_level = (level or "INFO").upper()
        with _CONFIG_LOCK:
            # Rebuild file sink
            if Logger._file_sink_id is not None:
                logr.remove(Logger._file_sink_id)
            Logger._file_sink_id = logr.add(
                sink=self.log_file,
                level=self.log_level,
                format=self._fmt(),
            )
            # Rebuild stderr sink if present
            if self.include_stderr:
                if Logger._stderr_sink_id is not None:
                    logr.remove(Logger._stderr_sink_id)
                Logger._stderr_sink_id = logr.add(
                    sink=stderr,
                    level=self.log_level,
                    format=self._fmt(),
                )


# -------------------------
# Decorators / trace helper
# -------------------------
def _log_trace(debug_message: str) -> None:
    """Logs an internal trace message.

    Args:
        debug_message: The message content to be logged at the TRACE level.
    """
    logr.trace(f"{Icons.bullet} {debug_message}")

def log_call(func: Callable[..., Any]) -> Callable[..., Any]:
    """Log a call's elapsed time and outcome at TRACE without logging its data.

    Coroutine and generator calls are measured through completion or closure,
    rather than just until the awaitable or iterator is created.

    Args:
        func: The function to be wrapped.

    Returns:
        Callable[..., Any]: The wrapped function.
    """
    name = f"{func.__module__}.{func.__qualname__}"

    def record(start: float, outcome: str, depth: int) -> None:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _log_trace(f"Call: {name} [{outcome}; elapsed {elapsed_ms:.2f} ms; depth {depth}]")

    if inspect.isasyncgenfunction(func):
        @functools.wraps(func)
        async def async_generator_wrapper(*args, **kwargs):
            start = time.perf_counter()
            depth = _CALL_DEPTH.get() + 1
            outcome = "closed"
            try:
                async with aclosing(_DepthAsyncIterator(func(*args, **kwargs), depth)) as iterator:
                    while True:
                        try:
                            item = await iterator.__anext__()
                        except StopAsyncIteration:
                            outcome = "ok"
                            break
                        yield item
            except GeneratorExit:
                raise
            except BaseException:
                outcome = "raised"
                raise
            finally:
                record(start, outcome, depth)

        return async_generator_wrapper

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            depth = _CALL_DEPTH.get() + 1
            token = _CALL_DEPTH.set(depth)
            outcome = "ok"
            try:
                return await func(*args, **kwargs)
            except BaseException:
                outcome = "raised"
                raise
            finally:
                _CALL_DEPTH.reset(token)
                record(start, outcome, depth)

        return async_wrapper

    if inspect.isgeneratorfunction(func):
        @functools.wraps(func)
        def generator_wrapper(*args, **kwargs):
            start = time.perf_counter()
            depth = _CALL_DEPTH.get() + 1
            outcome = "closed"
            try:
                yield from _DepthIterator(func(*args, **kwargs), depth)
                outcome = "ok"
            except GeneratorExit:
                raise
            except BaseException:
                outcome = "raised"
                raise
            finally:
                record(start, outcome, depth)

        return generator_wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        depth = _CALL_DEPTH.get() + 1
        token = _CALL_DEPTH.set(depth)
        outcome = "ok"
        try:
            return func(*args, **kwargs)
        except BaseException:
            outcome = "raised"
            raise
        finally:
            _CALL_DEPTH.reset(token)
            record(start, outcome, depth)

    return wrapper
