# logutil.py

# Author: Clive Bostock
# Date: 2024-06-22
# Description: General-purpose logging utility built on Loguru, with run ID support and decorators.

__title__ = 'Logging Library'
__author__ = "Clive Bostock"
__date__ = "2024-06-22"
__doc__ = """A general-purpose logging utility built on Loguru. Provides APIs for logging,
managing log levels, and tracing function calls."""

from pathlib import Path
import time
import functools
from typing import Callable, Any, Optional
from loguru import logger as logr
from sys import stderr
import os

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons

# Disable Loguru auto-init and preemptively remove stderr sink
os.environ["LOGURU_AUTOINIT"] = "0"
logr.remove()

APP_HOME = project_home()
DEFAULT_LOGS_DIR = APP_HOME / "logs"
CONFIG_DIR = APP_HOME / 'resources' / "config"
CONFIG_FILE = CONFIG_DIR / "orac.ini"

DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Global config manager
config_manager = ConfigManager(config_file_path=CONFIG_FILE)


class RunIDManager:
    _instance: Optional["RunIDManager"] = None
    _run_id: Optional[int] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._run_id = int(time.time())
        return cls._instance

    @property
    def run_id(self) -> str:
        return self.format_epoch_id(str(self._run_id))

    @staticmethod
    def format_epoch_id(epoch_id: str) -> str:
        if len(epoch_id) != 10 or not epoch_id.isdigit():
            raise ValueError("Epoch ID must be exactly 10 digits.")
        return f"{epoch_id[:2]}-{epoch_id[2:6]}-{epoch_id[6:]}"


run_id_manager = RunIDManager()
RUN_ID = run_id_manager.run_id


def log_stamp(post_underscore: bool = True, pref_underscore: bool = False) -> str:
    log_stamping = config_manager.bool_config_value(
        config_section='logging',
        config_key='log_stamping',
        default=False
    )
    _log_stamp = str(int(round(time.time() * 1000)))
    if post_underscore:
        _log_stamp += '_'
    if pref_underscore:
        _log_stamp = '_' + _log_stamp
    return _log_stamp if log_stamping else ''


class Logger:
    def __init__(self, log_file: Optional[Path] = None, log_level: str = "INFO"):
        self.log_file = log_file or DEFAULT_LOGS_DIR / f"r{RUN_ID}.log"
        self.log_level = log_level
        self.include_stderr = config_manager.bool_config_value(
            config_section='logging',
            config_key='inc_stderr',
            default=True
        )
        self._init_logger()

    def _init_logger(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        logr.remove()

        # File sink
        logr.add(
            sink=self.log_file,
            level=self.log_level,
            format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>"
        )
        logr.info(f"{Icons.tick} Logging initialized at {self.log_file}")

        # Optional stderr sink
        if self.include_stderr:
            logr.add(
                sink=stderr,
                level=self.log_level,
                format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>"
            )
            logr.debug(f"{Icons.info} Console logging ENABLED (stderr sink active)")
        else:
            logr.debug(f"{Icons.warn} Console logging DISABLED (stderr sink skipped)")

    def log_info(self, message: str):
        logr.info(f'{Icons.info} {message}')

    def log_debug(self, message: str):
        logr.debug(f'{Icons.idea} {message}')

    def log_warning(self, message: str):
        logr.warning(f'{Icons.warn} {message}')

    def log_error(self, message: str):
        logr.error(f'{Icons.error} {message}')

    def log_critical(self, message: str):
        logr.critical(f'{Icons.critical} {message}')


def _log_trace(debug_message: str) -> None:
    logr.trace(f'{Icons.bullet} {debug_message}')


def log_call(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        args_list = ", ".join(map(str, args))
        kwargs_list = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        params = f"({args_list}, {kwargs_list})" if kwargs else f"({args_list})"
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _log_trace(f"Call: {func.__name__}{params} [elapsed {elapsed_ms:.2f} ms]")
        return result

    return wrapper


# Example usage
if __name__ == '__main__':
    logger = OracLogger()
    logger.log_info("This is an info message")
    logger.log_debug("This is a debug message")
    logger.log_warning("This is a warning")
    logger.log_error("This is an error")
    logger.log_critical("This is critical")

    @log_call
    def sample_function(x: int, y: int) -> int:
        return x + y

    result = sample_function(5, 7)
    print(f"Result of sample_function: {result}")
