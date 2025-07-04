# Author: Clive Bostock
# Date: 2024-06-22
# Description: The ScenarioLogger module provides an abstraction layer to the Loguru library. It presents APIs for making
# logging calls as well as for managing logging operations.

__title__ = 'BDDS Logging Library'
__author__ = "Clive Bostock"
__date__ = "2024-06-22"
__doc__ = """The ScenarioLogger module provides an abstraction layer to the Loguru library. It presents APIs for making
logging calls as well as for managing logging operations."""

from loguru import logger as slogr
from pathlib import Path
import time
import functools
from typing import Callable, Any, Optional
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from sys import stderr
from os import getenv

APP_HOME = project_home()
DEFAULT_LOGS_DIR = APP_HOME / "logs"
CONFIG_DIR = APP_HOME / 'resources' / "config"
CONFIG_FILE = CONFIG_DIR / "bdds.ini"

DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Get custom login level colours
config_manager = ConfigManager(config_file_path=CONFIG_FILE)
supplementary_colour = config_manager.config_value(
    config_section='logger_instance',
    config_key='supplementary',
    default="light-green"
)

feature_colour = config_manager.config_value(
    config_section='logger_instance',
    config_key='feature',
    default="cyan"
)

scenario_colour = config_manager.config_value(
    config_section='logger_instance',
    config_key='scenario',
    default="light-blue"
)

scenario_completed_colour = config_manager.config_value(
    config_section='logger_instance',
    config_key='scenario_completed',
    default="light-blue"
)

inc_stderr = config_manager.bool_config_value(
    config_section='logger_instance',
    config_key='inc_stderr',
    default=True
)

# Configure custom log levels
slogr.level("FEATURE STARTED", no=31, color=f"<{feature_colour}>", icon="")
slogr.level("SCENARIO STARTED", no=32, color=f"<{scenario_colour}>", icon="")
slogr.level("SCENARIO COMPLETED", no=33, color=f"<{scenario_colour}>", icon="")
slogr.level("FEATURE COMPLETED", no=34, color=f"<{feature_colour}>", icon="")
slogr.level("SUPPLEMENTARY", no=35, color=f"<{supplementary_colour}>", icon="")

# Initialise the log stamp integer.
LOG_STAMP = int(round(time.time() * 1000))
LOG_SEP = '|'


def log_stamp(post_underscore: bool = True, pref_underscore: bool = False) -> str:
    """
    Returns a log stamp (time-based integer) if log_stamping is enabled in bdds.ini.

    Args:
        post_underscore (bool): If True, appends an underscore after the log stamp.
        pref_underscore (bool): If True, prepends an underscore before the log stamp.

    Returns:
        str: The log stamp string if log_stamping is enabled, else an empty string.
    """
    log_stamping = config_manager.config_value(
        config_section='logger_instance',
        config_key='log_stamping',
        default="n"
    )
    _log_stamp = LOG_STAMP
    if post_underscore:
        _log_stamp = str(_log_stamp) + '_'

    if pref_underscore:
        _log_stamp = '_' + str(_log_stamp)

    if log_stamping.lower() == 'y':
        return _log_stamp
    else:
        return ''


def _log_trace(debug_message: str) -> None:
    """
    Logs a trace-level debug message (private function).

    Args:
        debug_message (str): The debug message to log at trace level.
    """
    slogr.trace(f'{debug_message}')


def log_call(func):
    """
    Decorator to log the call (with parameters) to a function or method. Produces TRACE-level log output.

    Examples:
        @log_call
        def click_login(show_password: bool = False) -> str:
            ...

    Args:
        func (Callable): The function being decorated.

    Returns:
        Callable: The wrapper function that adds logging.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()  # Capture start time
        args_list = ", ".join(map(str, args))
        if args and kwargs:
            args_list = f"({args_list} {kwargs})"
        elif args:
            args_list = f"({args_list})"
        elif kwargs:
            args_list = f"({kwargs})"
        else:
            args_list = ""
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000  # Convert to milliseconds
        _log_trace(f"Call: {func.__name__}{args_list} [ela {elapsed_ms:.2f} ms]")
        return result

    return wrapper


def log_debug(debug_message: str) -> None:
    """
    Logs a debug-level message.

    Args:
        debug_message (str): The debug message to be logged.
    """
    slogr.debug(f'{debug_message}')


def log_hint(hint_message: str) -> None:
    """
    Logs a message at warning level as a 'hint'.

    Args:
        hint_message (str): The hint message to be logged.
    """
    slogr.warning(f'{hint_message}')


def log_info(info_message: str) -> None:
    """
    Logs an info-level message.

    Args:
        info_message (str): The informational message to be logged.
    """
    slogr.info(f'{info_message}')


class RunIDManager:
    """
    Manages a consistent run id (epoch-based) for the entire test run.
    """

    _instance: Optional["RunIDManager"] = None
    _run_id: Optional[int] = None  # Store the RUN_ID

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._run_id = int(time.time())  # Generate RUN_ID only once
        return cls._instance

    @property
    def run_id(self) -> str:
        """
        Returns the consistent RUN_ID, formatted with dashes.

        Returns:
            str: The formatted epoch-based run ID.
        """
        return self.format_epoch_id(epoch_id=str(self._run_id))

    @staticmethod
    def format_epoch_id(epoch_id: str) -> str:
        """
        Formats a 10-digit epoch ID into XX-XXXX-XXXX.

        Args:
            epoch_id (str): The epoch ID as a 10-digit string.

        Returns:
            str: The formatted ID with dashes.

        Raises:
            ValueError: If epoch_id is not exactly 10 digits or non-numeric.
        """
        if len(epoch_id) != 10 or not epoch_id.isdigit():
            raise ValueError("Epoch ID must be exactly 10 digits.")
        return f"{epoch_id[:2]}-{epoch_id[2:6]}-{epoch_id[6:]}"


run_id_manager = RunIDManager()
RUN_ID = run_id_manager.run_id


def screenshot_filename(step_descriptor: str) -> str:
    """
    Constructs a screenshot filename using the run ID.

    Args:
        step_descriptor (str): A descriptor of the step or context (e.g., 'login_page').

    Returns:
        str: A screenshot filename with run ID prefix.
    """
    return f'r{RUN_ID}_{step_descriptor}.png'


class ScenarioLogger:
    """
    A centralized logging utility for BDD scenarios with dynamic log file paths. Singleton pattern.
    """

    _instance: Optional["ScenarioLogger"] = None  # Singleton instance

    def __new__(cls, run_id: int = RUN_ID, log_dir: Optional[Path] = DEFAULT_LOGS_DIR,
                reset_instance: bool = False, log_level: str = None) -> "ScenarioLogger":

        """
        Controls instance creation to ensure a singleton, allowing log path customization.

        Args:
            run_id (int): The run ID for the logs.
            log_dir (Optional[Path]): The directory for log files. Defaults to DEFAULT_LOGS_DIR if None.
            reset_instance (bool): If True, resets the singleton instance, creating a new ScenarioLogger.

        Returns:
            ScenarioLogger: The initialized logger instance.
        """
        if cls._instance is None or reset_instance:
            cls._instance = super(ScenarioLogger, cls).__new__(cls)

            effective_log_dir = log_dir or DEFAULT_LOGS_DIR
            effective_log_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists


            log_file_path = effective_log_dir / f'r{run_id}_scenario.log'

            # Check whether the environment variable, BDDS_LOG_LEVEL is set to override
            # the log_level.
            bdds_log_level = getenv("BDDS_LOG_LEVEL", "NONE")
            if bdds_log_level != 'NONE':
                log_level = log_level

            if log_level is not None:
                cls._instance.init_logger(log_file_path, log_level=log_level)
            else:
                _log_level = config_manager.config_value(config_section='logger', config_key='log_level')
                cls._instance.init_logger(log_file_path, log_level=_log_level)

        return cls._instance

    def add_feature_finish_to_log(self, context):
        """
        Adds the 'feature completed' entry to the scenario log file. Intended for environment.py calls.

        Args:
            context: The Behave context or similar, containing PROJECT_ID, feature_filename, etc.
        """
        self._log_feature_completed(
            project_identifier=context.PROJECT_ID,
            feature_filename=context.feature_filename,
            supplementary=f'Run Id: {context.run_id}'
        )

    def add_scenario_finish_to_log(self, context):
        """
        Adds the 'scenario completed' entry to the scenario log file. Intended for environment.py calls.

        Args:
            context: The Behave context or similar, containing PROJECT_ID, scenario_name, etc.
        """
        test_duration = str(context.scenario_execution_time)
        test_run_status = context.scenario_run_status

        self._log_scenario_completed(
            project_identifier=context.PROJECT_ID,
            scenario_name=context.scenario_name,
            supplementary=f'Completion status: {test_run_status}'
        )
        self._log_scenario_completed(
            project_identifier=context.PROJECT_ID,
            scenario_name=context.scenario_name,
            supplementary=f'Scenario runtime: {test_duration}'
        )

    def log_feature_start(self, context):
        """
        Logs the start of a feature. Intended for environment.py calls.

        Args:
            context: The Behave context or similar, containing PROJECT_ID, feature_filename, etc.
        """
        self._log_feature_started(
            project_identifier=context.PROJECT_ID,
            feature_filename=context.feature_filename,
            supplementary=f'Run Id: {context.run_id}'
        )

    def log_scenario_start(self, context):
        """
        Logs the start of a scenario. Intended for environment.py calls.

        Args:
            context: The Behave context or similar, containing PROJECT_ID, feature_name, scenario_name, etc.
        """
        self._log_scenario_started(
            project_identifier=context.PROJECT_ID,
            feature_name=context.feature_name,
            scenario_name=context.scenario_name
        )

    def init_logger(self, log_path: Path, log_level: str = "INFO") -> None:
        """
        Initialises the logger with a specified log file path.

        Args:
            log_level (): Logging level, which should be one of TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL.
            log_path (Path): The path to the log file.
        """
        self.log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure log directory exists
        slogr.remove()  # Remove existing handlers
        self.log_sink_id = slogr.add(
            sink=log_path,
            level=log_level,
            format="<green>{time:DD/MM/YYYY HH:mm:ss UTC}</green> | "
                   "<level>{level: <8}</level> | <level>{message}</level>"
        )
        slogr.info(f"✅ Logging initialized at {log_path}")

        # Optionally add stderr sink based on configuration
        if inc_stderr:
            slogr.add(
                stderr,
                level=log_level.upper(),  # Instead of hardcoding "INFO"
                format="<green>{time:DD/MM/YYYY HH:mm:ss UTC}</green> | "
                       "<level>{level: <8}</level> | <level>{message}</level>"
            )

    @staticmethod
    def log_debug(message: str) -> None:
        """
        Logs a debug message.

        Args:
            message (str): The debug message to log.
        """
        slogr.debug(message)

    @staticmethod
    def log_error(message: str) -> None:
        """
        Logs an error message.

        Args:
            message (str): The error message to log.
        """
        slogr.error(message)

    @staticmethod
    def log_warning(message: str) -> None:
        """
        Logs a warning message.

        Args:
            message (str): The warning message to log.
        """
        slogr.warning(message)

    @staticmethod
    def log_info(message: str) -> None:
        """
        Logs an info-level message.

        Args:
            message (str): The informational message to log.
        """
        slogr.info(message)

    @staticmethod
    def step_supplementary(step_file_name: str, step_function: str, supplementary: str) -> None:
        """
        Logs a supplementary message at the custom "SUPPLEMENTARY" log level.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str): The supplementary text to log.
        """
        slogr.log("SUPPLEMENTARY",
                  f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary} {LOG_SEP}')

    @staticmethod
    def step_error(step_file_name: str, step_function: str, supplementary: str, info_supplementary='') -> None:
        """
        Logs a BDD step failure at the "ERROR" level with optional supplementary text.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str): The primary text for the error log.
            info_supplementary (str, optional): Additional info to log at SUPPLEMENTARY level.
        """
        slogr.error(f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary}')

        if info_supplementary:
            ScenarioLogger.step_supplementary(step_file_name=step_file_name,
                                              step_function=step_function,
                                              supplementary=info_supplementary)

    def set_log_level(self, level: str) -> None:
        """
        Updates the log level for the current sink.

        Args:
            level (str): A valid log level string, e.g., "DEBUG", "INFO", "TRACE", "WARNING", etc.
        """
        slogr.remove(self.log_sink_id)  # Remove the existing file sink
        self.log_sink_id = slogr.add(
            sink=self.log_path,
            level=level.upper(),
            format="<green>{time:DD/MM/YYYY HH:mm:ss UTC}</green> | "
                   "<level>{level: <8}</level> | <level>{message}</level>"
        )

        if inc_stderr:
            slogr.add(
                stderr,
                level=level.upper(),
                format="<green>{time:DD/MM/YYYY HH:mm:ss UTC}</green> | "
                       "<level>{level: <8}</level> | <level>{message}</level>"
            )

        slogr.info(f"🔁 Log level changed to {level.upper()}")

    @staticmethod
    def step_info(step_file_name: str, step_function: str, supplementary: str) -> None:
        """
        Logs a message at the regular "INFO" level.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str): The info text to log.
        """
        slogr.info(f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary}')

    @staticmethod
    def step_success(step_file_name: str, step_function: str, supplementary: str = '',
                     info_supplementary='') -> None:
        """
        Logs a BDD step success at the "SUCCESS" level, with optional supplementary text.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str, optional): The primary text for the success log.
            info_supplementary (str, optional): Additional info logged at the SUPPLEMENTARY level.
        """
        slogr.success(f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary}')

        if info_supplementary:
            ScenarioLogger.step_supplementary(step_file_name=step_file_name,
                                              step_function=step_function,
                                              supplementary=info_supplementary)

    @staticmethod
    def step_warning(step_file_name: str, step_function: str, supplementary: str = '',
                     info_supplementary='') -> None:
        """
        Logs a BDD step warning at the "WARNING" level, with optional supplementary text.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str, optional): The primary text for the warning log.
            info_supplementary (str, optional): Additional info logged at the SUPPLEMENTARY level.
        """
        slogr.warning(f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary}')

        if info_supplementary:
            ScenarioLogger.step_supplementary(step_file_name=step_file_name,
                                              step_function=step_function,
                                              supplementary=info_supplementary)

    @staticmethod
    def step_critical(step_file_name: str, step_function: str, supplementary: str = '',
                      info_supplementary='') -> None:
        """
        Logs a BDD step critical condition at the "CRITICAL" level, with optional supplementary text.

        Args:
            step_file_name (str): The filename of the step.
            step_function (str): The name of the step function.
            supplementary (str, optional): The primary text for the critical log.
            info_supplementary (str, optional): Additional info logged at the SUPPLEMENTARY level.
        """
        slogr.critical(f'{step_file_name} {LOG_SEP} {step_function} {LOG_SEP} {supplementary}')

        if info_supplementary:
            ScenarioLogger.step_supplementary(step_file_name=step_file_name,
                                              step_function=step_function,
                                              supplementary=info_supplementary)

    @staticmethod
    def log_call(func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorator to trace function calls and log execution time at TRACE level.

        Args:
            func (Callable[..., Any]): The function to decorate.

        Returns:
            Callable[..., Any]: The wrapped function with trace logging.
        """

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            args_list = ", ".join(map(str, args))

            if args and kwargs:
                args_list = f"({args_list}, {kwargs})"
            elif args:
                args_list = f"({args_list})"
            elif kwargs:
                args_list = f"({kwargs})"
            else:
                args_list = ""

            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000
            slogr.trace(f"Call: {func.__name__}{args_list} [Elapsed {elapsed_ms:.2f} ms]")
            return result

        return wrapper

    @staticmethod
    def _log_feature_completed(project_identifier: str, feature_filename: str,
                               supplementary: str = '') -> None:
        """
        Logs that a feature is completed at the custom "FEATURE COMPLETED" level.

        Args:
            project_identifier (str): The project identifier from configuration.
            feature_filename (str): The filename of the feature.
            supplementary (str, optional): Any additional text to log.
        """
        slogr.log("FEATURE COMPLETED",
                  f'{project_identifier} {LOG_SEP} {feature_filename} {LOG_SEP} {supplementary}')

    @staticmethod
    def _log_scenario_completed(project_identifier: str, scenario_name: str,
                                supplementary: str = '') -> None:
        """
        Logs that a scenario is completed at the custom "SCENARIO COMPLETED" level.

        Args:
            project_identifier (str): The project identifier.
            scenario_name (str): The scenario name.
            supplementary (str, optional): Any extra info to log.
        """
        slogr.log("SCENARIO COMPLETED",
                  f'{project_identifier} {LOG_SEP} {scenario_name} {LOG_SEP} {supplementary}')

    @staticmethod
    def _log_feature_started(project_identifier: str, feature_filename: str,
                             supplementary: str = '') -> None:
        """
        Logs that a feature is started at the custom "FEATURE STARTED" level.

        Args:
            project_identifier (str): The project identifier.
            feature_filename (str): The filename of the feature.
            supplementary (str, optional): Extra text to log.
        """
        slogr.log("FEATURE STARTED",
                  f'{project_identifier} {LOG_SEP} {feature_filename} {LOG_SEP} {supplementary}')

    @staticmethod
    def log_feature_info(project_identifier: str, feature_filename: str,
                         supplementary: str = '') -> None:
        """
        Logs an informational entry about a feature/scenario at the INFO level.

        Args:
            project_identifier (str): The project identifier.
            feature_filename (str): The filename of the feature.
            supplementary (str, optional): Extra info to log.
        """
        slogr.info(f'{project_identifier} {LOG_SEP} {feature_filename} {LOG_SEP} {supplementary}')

    @staticmethod
    def log_feature_warning(project_identifier: str, feature_filename: str,
                            supplementary: str = '') -> None:
        """
        Logs a warning entry about a feature/scenario at the WARNING level.

        Args:
            project_identifier (str): The project identifier.
            feature_filename (str): The filename of the feature.
            supplementary (str, optional): Extra info to log.
        """
        slogr.warning(f'{project_identifier} {LOG_SEP} {feature_filename} {LOG_SEP} {supplementary}')

    @staticmethod
    def log_feature_error(project_identifier: str, feature_filename: str,
                          supplementary: str = '') -> None:
        """
        Logs a warning entry about a feature/scenario at the ERROR level.

        Args:
            project_identifier (str): The project identifier.
            feature_filename (str): The filename of the feature.
            supplementary (str, optional): Extra info to log.
        """
        slogr.error(f'{project_identifier} {LOG_SEP} {feature_filename} {LOG_SEP} {supplementary}')

    @staticmethod
    def _log_scenario_started(project_identifier: str, feature_name: str,
                              scenario_name: str = '') -> None:
        """
        Logs that a scenario is started at the custom "SCENARIO STARTED" level.

        Args:
            project_identifier (str): The project identifier.
            feature_name (str): The feature name associated with the scenario.
            scenario_name (str, optional): The scenario name.
        """
        slogr.log("SCENARIO STARTED",
                  f'{project_identifier} {LOG_SEP} {feature_name} {LOG_SEP} {scenario_name}')


# ----------------------------------------------------------------------------------------------------------------------
# Example Usage
# ----------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    # Initialize logger_instance with a custom log path
    logger = ScenarioLogger(run_id=999, log_dir=Path("logs"))

    # Test: Basic Logging
    logger.log_info("This is an informational message.")
    logger.log_debug("This is a debug message.")

    logger.step_warning("test_steps.py", "user_login", "Potential issue encountered.")
    logger.step_error("test_steps.py", "user_login", "An error occurred while logging in.")
    logger.step_critical("test_steps.py", "user_login", "Critical failure during login process.")

    # Test: Scenario Logging
    logger._log_scenario_started("test_steps.py", "user_login", "User Authentication Feature")
    logger._log_scenario_completed("test_steps.py", "user_login", "User Authentication Feature")

    # Test: Success, Failure, and Supplementary Logs
    logger.step_success("test_steps.py", "step_function", "Scenario executed successfully.")
    logger.step_error("test_steps.py", "step_function", "Scenario encountered an error.")
    logger.step_supplementary("test_steps.py", "step_function", "Additional debug information.")

    logger.log_info("This message goes into the new log file.")


    # Test: Decorator for Function Logging
    @logger.log_call
    def sample_function(x: int, y: int) -> int:
        """
        Adds two integers.

        Args:
            x (int): The first integer.
            y (int): The second integer.

        Returns:
            int: The sum of x and y.
        """
        return x + y


    test_result = sample_function(5, 10)
    print(f"Result: {test_result}")  # Expected Output: 15

    # Test: Reset the Singleton Instance with a New Log Path
    logger = ScenarioLogger(run_id=999, log_dir=Path("logs"), reset_instance=True)
    logger.log_info("This message is in a completely new log instance.")

