__doc__ = """BDDS Test Utilities module. This file should be located in a lib directory below your main project folder.
The python files (.py) which are used for testing, need to import this file,
 using: 'from lib import bdds_testutl as butil'.
"""

import time
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from lib.loggerutl import ScenarioLogger
import json
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.framework_errors import InjectAnchorsFailure, InvalidParameter
from lib.loggerutl import screenshot_filename, slogr
from lib.session_manager import DBSession
from oracledb import DatabaseError
import sys
import os
from selenium.webdriver.remote.webdriver import WebDriver
from typing import Literal, cast
from typing import Any, Optional

logger = slogr

APP_HOME = project_home()
REPORTS_DIR = APP_HOME / "reports"
LOGS_DIR = APP_HOME / "logs"
SCREENSHOTS_DIR = APP_HOME / "screenshots"
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'bdds.ini'
ENV_MAPPING_FILE = APP_HOME / 'resources' / 'config' / 'env_mappings.ini'

conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
env_map_manager = ConfigManager(config_file_path=ENV_MAPPING_FILE)
SELENIUM_TIMEOUT = float(conf_manager.config_value(config_section='global', config_key='selenium_timeout'))
SELENIUM_TIMEOUT_SHORT = float(conf_manager.config_value(config_section='global', config_key='selenium_timeout_short'))
SELENIUM_TIMEOUT_COOKIES = float(conf_manager.config_value(config_section='global',
                                                           config_key='selenium_timeout_cookies'))

# Get the location of the scenario data management directory. The environment.py may make calls to
# to manage scenario data (e.g. tear down data, post-scenario. We only grab it here to check whether it exists
# in the before_feature hook function.
DATA_MGMT_DIR_RAW = conf_manager.config_value(config_section='data_mgmt', config_key='data_mgmt_location',
                                              default='features/data_mgmt')

if Path(DATA_MGMT_DIR_RAW).is_absolute():
    DATA_MGMT_DIR = Path(DATA_MGMT_DIR_RAW)
else:
    DATA_MGMT_DIR = APP_HOME / DATA_MGMT_DIR_RAW

BY_LOOKUP = {
    "id": By.ID,
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "name": By.NAME,
    "class": By.CLASS_NAME,
    "tag": By.TAG_NAME,
    "link": By.LINK_TEXT,
    "partial_link": By.PARTIAL_LINK_TEXT
}

JS_DIR = APP_HOME / 'js'
TIMEOUT_LIMIT: int = 10
TICK = '✅'
CROSS = CRITICAL = '❌'
IDEA = '💡'
INFO = 'ℹ️'
DOCS = '📘'
QUESTION = '❓'
NOTE = '❕'
ERROR = '❗'
BULLET = '•'
ARROW = '➤'
WARNING = '⚠️'

MESSAGE_RIGHT_PAD = 15
MESSAGE_MIN_LEN = 40
# When running in an IDE the following causes an exception.
try:
    MESSAGE_PAD_LENGTH = MESSAGE_MIN_LEN if (os.get_terminal_size()[0] - MESSAGE_RIGHT_PAD) < MESSAGE_MIN_LEN else \
        os.get_terminal_size()[0] - MESSAGE_RIGHT_PAD
except OSError:
    MESSAGE_PAD_LENGTH = 150

# Get the location of the scenario data management directory. The environment.py may make calls to
# to manage scenario data (e.g., tear down data, post-scenario.
DATA_MGMT_DIR = Path(conf_manager.config_value(config_section='data_mgmt', config_key='data_mgmt_location',
                                               default='features/data_mgmt'))

PROJECT_ID = conf_manager.config_value(config_section='global', config_key='project_identifier')

if DATA_MGMT_DIR.is_absolute():
    DATA_MGMT_DIR = DATA_MGMT_DIR
else:
    DATA_MGMT_DIR = APP_HOME / DATA_MGMT_DIR

import subprocess
from lib.framework_errors import SystemCommandError


def dotted_print(text: str, pad_length: int = MESSAGE_PAD_LENGTH) -> None:
    """Print a message which is right padded with dots, to a specified length.
    :param text: Text to print
    :type text: str
    :param pad_length: Length to right pad the string, using dots
    :type pad_length:
    """

    _message = text.ljust(pad_length, '.')
    sys.stdout.write(_message)
    sys.stdout.flush()


def dotted_print_done(text: str, pad_length: int = MESSAGE_PAD_LENGTH):
    """Works in conjunction with the dotted_print() function. Re-prints the message with " ✅" appended."""
    _message = text.ljust(pad_length, '.')
    sys.stdout.write("\r" + _message + f" {TICK}\n")


def dotted_print_fail(text: str, pad_length: int = MESSAGE_PAD_LENGTH):
    """Works in conjunction with the dotted_print() function. Re-prints the message with " ❌" appended."""
    _message = text.ljust(pad_length, '.')
    sys.stdout.write("\r" + _message + f" {CROSS}\n")


def run_cmd(command: list[str] | str, description: str, cwd: str | None = None,
            verbose: bool = False, shell: bool = False) -> subprocess.CompletedProcess:
    """
    Executes a system command with uniform logging and error handling.

    Args:
        command (list[str] | str): Command to execute, passed as a list of strings (recommended) or a string
            (required if shell=True).
        description (str): Textual description used for logging and user feedback.
        cwd (str | None): Directory in which to run the command. Defaults to None.
        verbose (bool): If True, prints the command's output to stdout. Defaults to False.
        shell (bool): If True, runs the command via the shell. Required if passing the command as a string
            with shell features (e.g. pipes). Defaults to False.

    Returns:
        subprocess.CompletedProcess: The result object from the completed subprocess.

    Raises:
        SystemCommandError: If the subprocess returns a non-zero exit code.
    """
    try:
        dotted_print(description)
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                check=True, cwd=cwd, shell=shell)
        if verbose and result.stdout:
            print(f"\n{description} output: {result.stdout.strip()}\n")
        if verbose and result.stderr:
            print(f"\n{description} stderr: {result.stderr.strip()}\n")
        dotted_print_done(description)
        return result
    except subprocess.CalledProcessError as e:
        dotted_print_fail(f"{description}\n")
        raise SystemCommandError(
            f"Command failed: {description}\n"
            f"Command: {command if isinstance(command, str) else ' '.join(command)}\n"
            f"Return code: {e.returncode}\n"
            f"Output: {e.stdout.strip()}\n"
            f"Error: {e.stderr.strip()}"
        ) from e


def os_mkdir(directory_path: Path | str, description: str, exist_ok=True):
    """
    Executes a create directory command with uniform logging and error handling.

    Args:

        directory_path (Path): The directory to be created
        description (str): Textual description used for logging and user feedback.
        exist_ok (bool): Don't error if the directory exists. Defaults to True.

    Returns:
        subprocess.CompletedProcess: The result object from the completed subprocess.

    Raises:
        SystemCommandError: If the subprocess returns a non-zero exit code.
    """
    try:
        dotted_print(description)
        os.makedirs(directory_path, exist_ok=exist_ok)
        dotted_print_done(description)
    except FileExistsError:
        dotted_print_fail(f"{description}\n")
        print(f"Directory '{directory_path}' already exists!")


def base_url(env_id: str = None) -> str:
    default_env = conf_manager.config_value(config_section='environment-default', config_key='base_url')
    if env_id:
        default_env = conf_manager.config_value(config_section=env_id, config_key='base_url')
    return default_env


def entrypoint_app_url(env_id: str) -> str:
    return conf_manager.config_value(config_section=f"environment-{env_id}", config_key='base_url')


def entrypoint_app_id(env_id: str = "default") -> str:
    return conf_manager.config_value(config_section=f"environment-{env_id}", config_key='app_id')


def log_screen_snapshot(driver, logger_instance, step_function: str, program: str,
                        severity: str = 'INFO', screenshots_dir: Path = SCREENSHOTS_DIR):
    """Typically used to process an exception. This function takes and logs associated screenshots. If not supplied,
    the default screenshots directory will be used.

    Args:
        driver (): WebDriver instance
        logger_instance (): Loguru logger instance
        step_function (): The step function associated with the output
        program (): The step file.
        severity (): Logging Severity: INFO, WARNING, ERROR, CRITICAL
        screenshots_dir ():

    """
    screenshot = screenshot_filename(step_descriptor=step_function)
    driver.save_screenshot(screenshots_dir / screenshot)
    # Not that bdds_orc/py is dependent on the 'screenshot taken' messages.
    if severity == 'INFO':
        logger_instance.step_info(step_file_name=program, step_function=step_function,
                                  supplementary=f'screenshot taken: {screenshot}')
    elif severity == 'ERROR':
        logger_instance.step_error(step_file_name=program, step_function=step_function,
                                   supplementary=f'screenshot taken: {screenshot}')
    elif severity == 'WARNING':
        logger_instance.step_warning(step_file_name=program, step_function=step_function,
                                     supplementary=f'screenshot taken: {screenshot}')
    elif severity == 'CRITICAL':
        logger_instance.step_critical(step_file_name=program, step_function=step_function,
                                      supplementary=f'screenshot taken: {screenshot}')
    else:
        raise InvalidParameter(message='Invalid severity level. Expected one of: INFO, WARNING, ERROR, CRITICAL')


def manage_scenario_data(scenario_logger: ScenarioLogger, database_session: DBSession, feature_filename: str,
                         phase: str, scenario_tag: str = None) -> int | None:
    """The manage_scenario_data accepts the context of the feature execution phase, along with established  scenario
    logger and database session instances. It then derives the names and paths of the files that would be required
    to execute PLSQL pertinent to the phase of execution. If a scenario tag is supplied, we assume that based on the
    provided phase ("before" or "after"), that we are looking for a files <scenario_tag>.<phase>.json and
    <scenario_tag>.<phase>.sql. If a scenario tag is not supplied, we assume that we are dealing with a "before" or
    "after" feature execution of PLSQL. The files are assumed to be found in
    <DATA_MGMT_DIR><feature_file.stem>.<phase>.json and <DATA_MGMT_DIR><feature_file.stem>.<phase>.sql where
    <feature_file.stem> is the name of the feature file with the .feature extension removed. If the resolved files are
    found, then they are executed; otherwise we do nothing.

    Args:
        scenario_logger (): ScenarioLogger instance, originating from environment.py
        database_session (): DatabaseSession instance, originating from environment.py
        feature_filename (): Feature file name
        phase (): Execution phase ("before" or "after")
        scenario_tag (): The scenario tag - None for feature level executions
        """
    if phase not in ['before', 'after']:
        raise InvalidParameter(message='Invalid phase. Expected one of "before" or "after"')

    feature = feature_filename.replace('.feature', '')
    files_location = DATA_MGMT_DIR / feature
    json_file = files_location / f'{feature}.{phase}.json' if scenario_tag is None else files_location / f'{scenario_tag}.{phase}.json'
    plsql_file = files_location / f'{feature}.{phase}.sql' if scenario_tag is None else files_location / f'{scenario_tag}.{phase}.sql'
    bind_mappings = {}
    if not json_file.exists():
        return -20001

    if not plsql_file.exists():
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'A data cleanup JSON file, "{json_file.name}", was found, '
                                                          f'without a complementary SQL file - cleanup skipped')
        return -20002

    try:
        with open(json_file, "r", encoding="utf-8") as file:
            bind_mappings = json.load(file)
    except FileNotFoundError:
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'Unable to open JSON file, "{json_file.name}" - '
                                                          f'cleanup operation skipped.')
        return -20003
    except json.JSONDecodeError:
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'The file "{json_file.name}", contains invalid JSON - '
                                                          f'cleanup operation skipped.')
        return -20004

    try:
        with open(plsql_file, "r", encoding="utf-8") as file:
            plsql = file.read()
    except FileNotFoundError:
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'Unable to open PLSQL file, "{plsql_file.name}" - '
                                                          f'cleanup operation skipped.')
        return -20005

    if ':b_status' not in plsql:
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'The PLSQL file, "{plsql_file.name}", does not contain a '
                                                          f'status bind variable (:status) - '
                                                          f'cleanup operation skipped.')
        return -20006

    # Add the required status (in case it is missing)
    bind_mappings['b_status'] = 0
    try:
        database_session.run_plsql_block(plsql_block=plsql, bind_mappings=bind_mappings)
    except DatabaseError as e:
        print(f'Error executing PL/SQL block:\n{e}')
        print(f'Error code block:\n{plsql}')
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'The PLSQL file, "{plsql_file.name}", execution failed!')
    if bind_mappings['b_status']:
        scenario_logger.log_feature_warning(project_identifier=PROJECT_ID,
                                            feature_filename=feature_filename,
                                            supplementary=f'The data management PLSQL file, "{plsql_file.name}", '
                                                          f'execution failed, with status {bind_mappings["b_status"]}')

        return bind_mappings['b_status']
    else:
        scenario_logger.log_feature_info(project_identifier=PROJECT_ID,
                                         feature_filename=feature_filename,
                                         supplementary=f'The data management PLSQL file, "{plsql_file.name}", executed '
                                                       f'successfully')
        return 0


def process_step_error(driver, logger_instance, step_function: str, program: str,
                       exception: Exception | str = None, screenshots_dir: Path = SCREENSHOTS_DIR):
    """Typically used to process a step error. This function takes and logs associated screenshots. If not supplied,
    the default screenshots directory will be used. Use for mitigated step exception (e.g., assertion failures)

    Args:
        driver (): Selenium webdriver instance
        logger_instance (): Scenario logger instance
        step_function (): Step function name
        program (): The step program name
        exception (): Exception in string format
        screenshots_dir (): Location of the screenshots directory
    """
    log_screen_snapshot(driver=driver, logger_instance=logger_instance, step_function=step_function,
                        program=program, severity='ERROR', screenshots_dir=screenshots_dir)

    if exception:
        logger_instance.step_error(step_file_name=program, step_function=step_function,
                                   supplementary=f'Exception raised:\n {str(exception)}')


def process_step_critical(driver, logger_instance, step_function: str, program: str,
                          exception: Exception | str = None, screenshots_dir: Path = SCREENSHOTS_DIR):
    """Typically used to process an exception. This function takes and logs associated screenshots. If not supplied,
    the default screenshots directory will be used. Use for Selenium-based exceptions. Use for catastrophic step
    exceptions.

    Args:
        driver (): Selenium webdriver instance
        logger_instance (): Scenario logger instance
        step_function (): Step function name
        program (): The step program name
        exception (): Exception in string format
        screenshots_dir (): Location of the screenshots directory
    """
    log_screen_snapshot(driver=driver, logger_instance=logger_instance, step_function=step_function,
                        program=program, severity='CRITICAL', screenshots_dir=screenshots_dir)

    if exception:
        logger_instance.step_critical(step_file_name=program, step_function=step_function,
                                      supplementary=f'Exception raised:\n {str(exception)}')


def inject_anchors(driver: webdriver):
    js_path = JS_DIR / 'injectAnchors.js'
    try:
        v_js = _return_anchors_javascript(js_path=js_path)
        driver.execute_script(v_js)
    except FileNotFoundError:
        raise InjectAnchorsFailure(f"ERROR: Unable to locate the injectAnchors.js script: {js_path}")
    except JavascriptException as e:
        print(f"JavaScript error: {e}")


def set_http_headers(driver: webdriver, env: str):
    """
    Set HTTP headers for user, roles etc., only if needed.
    Caches previous values to avoid redundant CDP calls.
    """

    set_chrome_http_headers = conf_manager.bool_config_value(
        config_section='browser',
        config_key='set_chrome_http_headers',
        default=False
    )
    if not set_chrome_http_headers:
        return

    # Resolve desired headers
    desired_headers = {
        "x-auth-uid": env_map_manager.config_value(config_section=env, config_key='x-auth-uid'),
        "x-auth-name": env_map_manager.config_value(config_section=env, config_key='x-auth-name'),
        "x-dggiaapproles": env_map_manager.config_value(config_section=env, config_key='x-dggiaapproles')
    }

    # Flag: Enable network only once
    if not hasattr(driver, "_cdp_network_enabled"):
        driver.execute_cdp_cmd("Network.enable", {})
        driver._cdp_network_enabled = True

    # Avoid redundant re-setting if the headers are unchanged
    current_headers = getattr(driver, "_extra_http_headers", {})
    if current_headers == desired_headers:
        return  # No change — skip CDP command

    # Set the headers and cache them on the driver instance
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": desired_headers})
    driver._extra_http_headers = desired_headers


def _return_anchors_javascript(js_path: Path) -> str:
    with open(js_path, 'r') as file:
        return file.read().strip()


def sleep(secs: int | float = 1, context=None):
    if context and context.headless:
        return
    if conf_manager.config_value(config_section='global', config_key='allow_sleeps', default="n").lower() == 'y':
        time.sleep(secs)


def wait_element_clickable(driver: WebDriver,
                           by_method: Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"],
                           selector: str,
                           wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be clickable using the specified locating strategy.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        by_method (Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"]):
            Locating strategy used to find the element.
        selector (str): The selector string used to locate the element.
        wait_time (float | int, optional): Maximum time to wait for the element. Defaults to SELENIUM_TIMEOUT.

    Returns:
        WebElement: The located WebElement once it is clickable.

    Raises:
        TimeoutException: If the element is not clickable within the wait time.
    """

    by_lookup = {
        "id": By.ID,
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "name": By.NAME,
        "class": By.CLASS_NAME,
        "tag": By.TAG_NAME,
        "link": By.LINK_TEXT,
        "partial_link": By.PARTIAL_LINK_TEXT
    }

    by = by_lookup.get(by_method.lower())
    if not by:
        raise ValueError(f"Unsupported by_method: {by_method}")

    return WebDriverWait(driver, wait_time).until(ec.element_to_be_clickable((by, selector)))


def wait_element_presence(driver: WebDriver,
                          by_method: Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"],
                          selector: str,
                          wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be present in the DOM using the specified locating strategy.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        by_method (Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"]):
            Locating strategy used to find the element.
        selector (str): The selector string used to locate the element.
        wait_time (float | int, optional): Maximum time to wait for the element. Defaults to SELENIUM_TIMEOUT.

    Returns:
        WebElement: The located WebElement.

    Raises:
        TimeoutException: If the element is not found in time.
    """
    by = BY_LOOKUP.get(by_method.lower())
    if not by:
        raise ValueError(f"Unsupported by_method: {by_method}")

    return WebDriverWait(driver, wait_time).until(ec.presence_of_element_located((by, selector)))


def wait_element_visibility(driver: WebDriver,
                            by_method: Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"],
                            selector: str,
                            wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element using the specified locating strategy.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        by_method (Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"]):
            Locating strategy used to find the element.
        selector (str): The selector string used to locate the element.
        wait_time (float | int, optional): Maximum time to wait for the element. Defaults to SELENIUM_TIMEOUT.
        visible (bool, optional): Whether to wait for visibility (True) or just presence (False). Defaults to False.

    Returns:
        WebElement: The located WebElement.

    Raises:
        TimeoutException: If the element is not found in time.
    """


    by = BY_LOOKUP.get(by_method.lower())
    if not by:
        raise ValueError(f"Unsupported by_method: {by_method}")

    return WebDriverWait(driver, wait_time).until(ec.visibility_of_element_located((by, selector)))


def wait_element_invisibility(driver: WebDriver,
                              by_method: Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"],
                              selector: str,
                              wait_time: float | int = 10) -> bool:
    """
    Waits for an element to become invisible using the specified locating strategy.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        by_method (Literal["id", "xpath", "css", "name", "class", "tag", "link", "partial_link"]):
            Locating strategy used to find the element.
        selector (str): The selector string used to locate the element.
        wait_time (float | int, optional): Maximum time to wait for the element to become invisible.
            Defaults to SELENIUM_TIMEOUT.

    Returns:
        bool: True if the element becomes invisible within the wait time, False otherwise.

    Raises:
        TimeoutException: If the element does not become invisible in time.
    """


    by = BY_LOOKUP.get(by_method.lower())
    if not by:
        raise ValueError(f"Unsupported by_method: {by_method}")

    result = WebDriverWait(driver, wait_time).until(
        ec.invisibility_of_element_located((by, selector))
    )

    return cast(bool, result)


def sanitise_value(string: str) -> str:
    """
    Removes commas, hyphens, and whitespace from a string.

    Args:
        string (str): The input string to sanitise.

    Returns:
        str: The sanitised string.
    """
    return re.sub(r"[,\-\s]", "", string)


def wait_clickable_element_by_css(driver, element_selector: str,
                                  wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be clickable using a CSS selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): CSS selector string.
        wait_time (float | int, optional): Maximum wait time. SELENIUM_TIMEOUT is the default timeout.

    Returns:
        WebElement: The clickable element.
    """
    return WebDriverWait(driver, wait_time).until(ec.element_to_be_clickable((By.CSS_SELECTOR, element_selector)))


def wait_clickable_element_by_id(driver, element_selector: str,
                                 wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be clickable using an ID selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): ID selector string.
        wait_time (float | int, optional): Maximum wait time. This defaults to SELENIUM_TIMEOUT.

    Returns:
        WebElement: The clickable element.
    """
    return WebDriverWait(driver, wait_time).until(ec.element_to_be_clickable((By.ID, element_selector)))


def wait_load_element_by_id(driver, element_selector: str, wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be present in the DOM using an ID selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): ID selector string.
        wait_time (float | int, optional): Maximum wait time. SELENIUM_TIMEOUT is the default timeout.

    Returns:
        WebElement: The located element.
    """
    return WebDriverWait(driver, wait_time).until(ec.presence_of_element_located((By.ID, element_selector)))


def wait_element_visibility_by_id(driver, element_selector: str,
                                  wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be visible using an ID selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): ID selector string.
        wait_time (float | int, optional): Maximum wait time. SELENIUM_TIMEOUT is the default timeout.

    Returns:
        WebElement: The visible element.
    """
    return WebDriverWait(driver, wait_time).until(ec.visibility_of_element_located((By.ID, element_selector)))


def wait_load_element_by_css(driver, element_selector: str, wait_time: float | int = SELENIUM_TIMEOUT) -> WebElement:
    """
    Waits for an element to be present in the DOM using a CSS selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): CSS selector string.
        wait_time (float | int, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT.

    Returns:
        WebElement: The located element.
    """
    return WebDriverWait(driver, wait_time).until(ec.presence_of_element_located((By.CSS_SELECTOR, element_selector)))


def wait_element_visibility_by_class(driver, element_selector: str,
                                     timeout: float = SELENIUM_TIMEOUT_SHORT) -> WebElement:
    """
    Waits for an element to be visible using a class name selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): Class name selector string.
        timeout (float, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT_SHORT.

    Returns:
        WebElement: The visible element.
    """
    return WebDriverWait(driver, timeout).until(
        ec.visibility_of_element_located((By.CLASS_NAME, element_selector)))


def wait_element_invisibility_by_class(driver, element_selector: str,
                                       timeout: float = SELENIUM_TIMEOUT_SHORT) -> WebElement:
    """
    Waits for an element to become invisible using a class name selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): Class name selector string.
        timeout (float, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT_SHORT.

    Returns:
        WebElement: The previously visible element, now invisible.
    """
    return WebDriverWait(driver, timeout).until(
        ec.invisibility_of_element_located((By.CLASS_NAME, element_selector)))


def wait_spinner_invisibility(driver, spinner_class: str = 'u-Processing-spinner',
                              timeout: float = SELENIUM_TIMEOUT_SHORT):
    """
    Waits for a spinner element to become invisible.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        spinner_class (str, optional): CSS class of the spinner. Defaults to 'u-Processing-spinner'.
        timeout (float, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT_SHORT.
    """
    wait_element_invisibility_by_class(driver, spinner_class)


def wait_spinner_visibility(driver, spinner_class: str = 'u-Processing-spinner'):
    """
    Waits for a spinner element to become visible.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        spinner_class (str, optional): CSS class of the spinner. Defaults to 'u-Processing-spinner'.
    """
    wait_element_visibility_by_class(driver, spinner_class)


def wait_element_invisibility_by_css(driver, element_selector: str,
                                     timeout: float = SELENIUM_TIMEOUT_SHORT) -> WebElement:
    """
    Waits for an element to become invisible using a CSS selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): CSS selector string.
        timeout (float, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT_SHORT.

    Returns:
        WebElement: The previously visible element, now invisible.
    """
    return WebDriverWait(driver, timeout).until(
        ec.invisibility_of_element_located((By.CSS_SELECTOR, element_selector)))


def wait_element_visibility_by_css(driver, element_selector: str,
                                   timeout: float = SELENIUM_TIMEOUT_SHORT) -> WebElement:
    """
    Waits for an element to be visible using a CSS selector.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element_selector (str): CSS selector string.
        timeout (float, optional): Maximum wait time. Defaults to SELENIUM_TIMEOUT_SHORT.

    Returns:
        WebElement: The visible element.
    """
    return WebDriverWait(driver, timeout).until(
        ec.visibility_of_element_located((By.CSS_SELECTOR, element_selector)))


def wait_for_alert(driver, timeout: float = SELENIUM_TIMEOUT_SHORT):
    """
    Waits for a JavaScript alert to be present.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        timeout (float, optional): Maximum wait time. SELENIUM_TIMEOUT is the default timeout.
    """
    WebDriverWait(driver, timeout).until(ec.alert_is_present())


def scroll_and_select(driver, element):
    """
    Scrolls to an element and clicks it.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        element (WebElement): The element to scroll to and click.
    """
    ActionChains(driver).move_to_element(element).perform()
    element.click()



from abc import ABC, abstractmethod
from selenium.webdriver import Keys

class AbsPage(ABC):
    """
    Abstract base class for all APEX page objects, enforcing a verify_page method implementation.
    """

    @abstractmethod
    def verify_page(self):
        """
        Abstract method that verifies the page has loaded correctly. If not verified, an exception is propagated.
        """
        pass

class BasePage:
    """Base class providing common Selenium page interaction methods."""

    EXPLICIT_WAIT_TIMEOUT: int = 30

    def __init__(self, driver: WebDriver):
        """
        Initializes the page with a Selenium WebDriver.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.
        """
        self.driver = driver

    def wait_element_to_be_visible(self, element: WebElement, timeout: int = EXPLICIT_WAIT_TIMEOUT) -> WebElement:
        """
        Waits until the specified element is visible.

        Args:
            element (WebElement): The element to wait for.
            timeout (int): Maximum wait time in seconds.

        Returns:
            WebElement: The visible WebElement.
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(ec.visibility_of(element))

    def wait_element_to_be_clickable(self, element: WebElement, timeout: int = EXPLICIT_WAIT_TIMEOUT) -> WebElement:
        """
        Waits until the specified element is clickable.

        Args:
            element (WebElement): The element to wait for.
            timeout (int): Maximum wait time in seconds.

        Returns:
            WebElement: The clickable WebElement.
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(ec.element_to_be_clickable(element))

    def wait_element_then_click(self, element: WebElement, timeout: int = EXPLICIT_WAIT_TIMEOUT) -> None:
        """
        Waits until the element is clickable, then clicks it.

        Args:
            element (WebElement): The element to click.
            timeout (int): Maximum wait time in seconds.
        """
        self.wait_element_to_be_clickable(element, timeout).click()

    def check_page_title(self, expected_title: str) -> None:
        """
        Asserts that the page title matches the expected title.

        Args:
            expected_title (str): The expected page title.

        Raises:
            AssertionError: If the title does not match within the timeout.
        """
        wait = WebDriverWait(self.driver, self.EXPLICIT_WAIT_TIMEOUT)
        assert wait.until(ec.title_is(expected_title)) is True

    def wait_element_and_send_keys(self, element: WebElement, keys: str) -> None:
        """
        Waits for the element to be visible, clears it, sends keys, and presses Enter.

        Args:
            element (WebElement): The input field WebElement.
            keys (str): The keys to send.
        """
        input_field: WebElement = self.wait_element_to_be_visible(element)
        input_field.clear()
        input_field.send_keys(keys)
        input_field.send_keys(Keys.ENTER)

    def select_option_by_value(self, element: WebElement, list_value: list[str]) -> None:
        """
        Selects multiple options from a dropdown by their values.

        Args:
            element (WebElement): The <select> element.
            list_value (list[str]): List of option values to select.
        """
        select = Select(self.wait_element_to_be_visible(element))
        for value in list_value:
            select.select_by_value(value)

    def deselect_option_by_value(self, element: WebElement, list_value: list[str]) -> None:
        """
        Deselects multiple options from a dropdown by their values.

        Args:
            element (WebElement): The <select> element.
            list_value (list[str]): List of option values to deselect.
        """
        select = Select(self.wait_element_to_be_visible(element))
        for value in list_value:
            select.deselect_by_value(value)

    def get_web_element(self, by_methode: str, locator: str, timeout: int = EXPLICIT_WAIT_TIMEOUT) -> WebElement:
        """
        Retrieves a visible WebElement using a locator.

        Args:
            by_methode (str): Locator strategy (e.g., By.ID, By.XPATH).
            locator (str): The locator string.
            timeout (int): Maximum wait time in seconds.

        Returns:
            WebElement: The found WebElement.
        """
        wait = WebDriverWait(self.driver, timeout)
        wait.until(ec.visibility_of_element_located((by_methode, locator)))
        return self.driver.find_element(by_methode, locator)

    def get_web_elements(self, by_methode: str, locator: str, timeout: int = EXPLICIT_WAIT_TIMEOUT) -> list[WebElement]:
        """
        Retrieves a list of visible WebElements using a locator.

        Args:
            by_methode (str): Locator strategy (e.g., By.CLASS_NAME, By.XPATH).
            locator (str): The locator string.
            timeout (int): Maximum wait time in seconds.

        Returns:
            list[WebElement]: A list of matching WebElements.
        """
        wait = WebDriverWait(self.driver, timeout)
        wait.until(ec.visibility_of_all_elements_located((by_methode, locator)))
        return self.driver.find_elements(by_methode, locator)


class BaseDBService:
    """
    Base class for service-layer DB logic. Provides standard methods for executing SQL or PL/SQL,
    and fetching results in common formats.

    Attributes:
        db (DBSession): Active database session for executing queries.
    """

    def __init__(self, db_session: DBSession):
        """
        Initialises the BaseDBService with a database session.

        Args:
            db_session (DBSession): Active DBSession object, usually from context.db_session.
        """
        self.db = db_session

    def execute_sql(self, sql: str, bind_vars: Optional[dict[str, Any]] = None) -> None:
        """
        Executes a SQL DML statement (INSERT, UPDATE, DELETE) without returning results.

        Args:
            sql (str): The SQL statement to execute.
            bind_vars (Optional[dict[str, Any]]): Bind variable mappings, if any.

        Example:
            ```python
            sql = "UPDATE employees SET salary = salary * 1.1 WHERE department_id = :dept"
            bind_vars = {"dept": 10}
            service.execute_sql(sql, bind_vars)
            ```
        """
        self.db.execute(sql, bind_vars=bind_vars)

    def fetch_all(self, sql: str, bind_vars: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """
        Executes a SQL SELECT and returns all rows as a list of dictionaries.

        Args:
            sql (str): The SELECT query to execute.
            bind_vars (Optional[dict[str, Any]]): Bind variable mappings, if any.

        Returns:
            list[dict[str, Any]]: List of result rows as dictionaries.

        Example:
            ```python
            sql = "SELECT employee_id, last_name FROM employees WHERE department_id = :dept"
            bind_vars = {"dept": 10}
            result = service.fetch_all(sql, bind_vars)
            ```
        """
        return self.db.dict_sql_dataset(sql, bind_vars=bind_vars)

    def fetch_one(self, sql: str, bind_vars: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
        """
        Executes a SQL SELECT and returns the first row as a dictionary.

        Args:
            sql (str): The SELECT query to execute.
            bind_vars (Optional[dict[str, Any]]): Bind variable mappings, if any.

        Returns:
            Optional[dict[str, Any]]: The first row as a dictionary, or None if no rows.

        Example:
            ```python
            sql = "SELECT email FROM users WHERE user_id = :uid"
            bind_vars = {"uid": 42}
            user = service.fetch_one(sql, bind_vars)
            ```
        """
        rows = self.db.dict_sql_dataset(sql, bind_vars=bind_vars)
        return rows[0] if rows else None

    def fetch_column(self, sql: str, bind_vars: Optional[dict[str, Any]] = None) -> list[Any]:
        """
        Executes a SQL SELECT and returns the first column from all rows as a list.

        Args:
            sql (str): The SELECT query to execute.
            bind_vars (Optional[dict[str, Any]]): Bind variable mappings, if any.

        Returns:
            list[Any]: Values from the first column of each result row.

        Example:
            ```python
            sql = "SELECT username FROM users WHERE active = 1"
            usernames = service.fetch_column(sql)
            ```
        """
        return self.db.column_sql_dataset(sql, bind_vars=bind_vars)

    def run_plsql_block(self, plsql_block: str, bind_vars: Optional[dict[str, Any]] = None) -> None:
        """
        Executes an anonymous PL/SQL block with optional bind variables.

        Args:
            plsql_block (str): The PL/SQL block to run.
            bind_vars (Optional[dict[str, Any]]): Bind variable mappings, including OUT binds like `b_status`.

        Raises:
            PLSQLScriptError: If `b_status` is present and indicates failure.

        Example:
            ```python
            plsql = '''
            BEGIN
                update_log(:msg);
            END;
            '''
            service.run_plsql_block(plsql, {"msg": "Job started"})
            ```
        """
        self.db.run_plsql_block(plsql_block, bind_mappings=bind_vars or {})

