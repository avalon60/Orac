# Python Standards

## Purpose

This document defines Python coding standards for Orac.

These standards apply to Python application code, command line tools,
plugin framework code, plugin implementations, tests, and supporting
scripts.

The goals are:

- readable code
- predictable structure
- safe plugin loading
- consistent logging
- maintainable command line interfaces
- clear typing
- useful docstrings
- low surprise for human developers and coding agents

Where these standards conflict with local project code that already
exists, preserve the existing working pattern unless explicitly asked to
refactor it.

---

## Core rules

- Follow PEP 8 unless this document defines an Orac-specific rule.
- Use 4 spaces for Python indentation.
- Do not use hard tabs.
- Use British English in comments and documentation.
- Prefer small, focused functions.
- Use type hints for public functions, methods, and important internal
  helpers.
- Use Google-style docstrings by default.
- Use NumPy-style docstrings only for data science code where explicitly
  appropriate.
- Use `argparse` for command line arguments.
- Use Loguru for application logging.
- Do not use `print()` for normal processing, diagnostics, or errors.
- Prefer static imports for normal code.
- Use dynamic imports only for controlled framework-level mechanisms,
  such as Orac plugin loading.
- Do not use wildcard imports.
- Do not log secrets.
- Do not store secrets in source code.

---

## File layout

Python files should use this order:

1. shebang, if executable
2. encoding comment, only if needed
3. module docstring
4. `__future__` imports
5. standard library imports
6. third-party imports
7. local imports
8. constants
9. module globals
10. exceptions
11. type aliases
12. private helpers
13. public functions
14. classes
15. command line entrypoint helpers
16. `main()`
17. main guard

Example:

```python
#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 2026-04-26
# Description: Demonstrates the preferred Orac Python module layout.
"""Demonstrate the preferred Orac Python module layout.

This module shows the expected ordering of imports, constants, helper
functions, public functions, classes, and command line entrypoint logic.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from loguru import logger

from orac.example import helpers


DEFAULT_LIMIT: int = 100


def _normalise_name(name: str) -> str:
    """Normalise a name for comparison.

    Args:
        name (str): Name to normalise.

    Returns:
        str: Normalised name.
    """
    return name.strip().lower()


def process_names(names: Iterable[str]) -> list[str]:
    """Process a collection of names.

    Args:
        names (Iterable[str]): Names to process.

    Returns:
        list[str]: Normalised names.
    """
    return [_normalise_name(name=name) for name in names]


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="orac-example",
        description="Demonstrate the Orac Python CLI pattern.",
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Input file path.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of records to process.",
    )

    return parser


def main() -> int:
    """Run the command line entrypoint.

    Returns:
        int: Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args()

    logger.info("Processing {}", args.input_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Module headers

Executable Python scripts must include a simple header immediately after
the shebang.

Required fields:

```python
#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 2026-04-26
# Description: Describe the purpose of the script.
"""Short one-line summary of the module.

Longer description explaining the purpose of the module, its
responsibilities, and any important context or usage notes.
"""
```

Importable modules without a shebang should still include the module
docstring at the top of the file.

Example:

```python
"""Database session utilities.

This module provides helpers for managing database connections,
transactions, and retry logic.
"""
```

Do not add corporate copyright blocks unless explicitly instructed.

---

## Line length

Use these limits as guidance:

| Content | Preferred limit |
|---|---:|
| Code | 79 characters |
| Comments | 72 characters |
| Docstrings | 72 characters |

Where readability is clearly improved, code lines may exceed 79
characters, but avoid very long lines.

Do not produce heavily wrapped code that becomes harder to read.

---

## Imports

Import order:

1. standard library
2. third-party packages
3. local application imports

Use a blank line between import groups.

Good:

```python
import argparse
from pathlib import Path

from loguru import logger

from orac.config import ConfigManager
from orac.plugins import PluginRegistry
```

Bad:

```python
from orac.plugins import PluginRegistry
import argparse
from loguru import logger
from pathlib import Path
```

Rules:

- One import per line.
- No wildcard imports.
- Prefer importing modules over many individual names.
- Import specific names where it clearly improves readability.
- Keep imports at the top of the file unless there is a clear reason not
  to.
- Optional or slow dependencies may be imported inside functions if the
  failure path is clear.

Good:

```python
from pathlib import Path
```

Acceptable optional dependency pattern:

```python
try:
    import orjson as json
except ImportError:
    import json
```

For optional dependencies inside functions:

```python
def load_yaml(path: Path) -> dict[str, object]:
    """Load a YAML file.

    Args:
        path (Path): YAML file path.

    Returns:
        dict[str, object]: Parsed YAML content.

    Raises:
        RuntimeError: If PyYAML is not installed.
    """
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to load YAML configuration files."
        ) from exc

    with path.open("r", encoding="utf-8") as file_obj:
        return yaml.safe_load(file_obj) or {}
```

---

## Dynamic imports and plugin loading

Static imports are preferred for normal application code.

Dynamic imports are permitted only where there is a clear framework-level
reason, such as loading declared Orac plugins.

Dynamic imports must be centralised in the plugin runtime or discovery
layer.

Do not scatter ad hoc dynamic imports throughout the codebase.

Dynamic imports must not be used as a convenience shortcut.

When using dynamic imports:

- Use `importlib`.
- Do not use `exec`.
- Do not use `eval`.
- Do not import arbitrary user-provided module names.
- Validate plugin identifiers before constructing import paths.
- Accept only lowercase snake_case plugin identifiers.
- Load only from approved plugin locations.
- Require a known plugin entrypoint or provider contract.
- Fail with clear structured errors.
- Log the plugin id, module path, and safe failure reason.
- Do not log secrets or full configuration values.
- Do not use dynamic imports to bypass plugin registration, security, or
  dependency rules.

A valid plugin import path must be derived from registered plugin
metadata, not directly from raw user input.

Good:

```python
import importlib
import re
from types import ModuleType


PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def is_valid_plugin_id(plugin_id: str) -> bool:
    """Return whether a plugin id is valid.

    Args:
        plugin_id (str): Candidate plugin identifier.

    Returns:
        bool: True when the plugin id is valid.
    """
    return bool(PLUGIN_ID_PATTERN.fullmatch(plugin_id))


def load_plugin_module(plugin_id: str) -> ModuleType:
    """Load a registered plugin module.

    Args:
        plugin_id (str): Validated lowercase snake_case plugin
            identifier.

    Returns:
        ModuleType: Imported plugin module.

    Raises:
        ValueError: If the plugin identifier is invalid.
        ImportError: If the plugin module cannot be imported.
    """
    if not is_valid_plugin_id(plugin_id=plugin_id):
        raise ValueError(f"Invalid plugin id: {plugin_id}")

    module_name = f"plugins.{plugin_id}.provider"
    return importlib.import_module(module_name)
```

Bad:

```python
exec(user_supplied_code)

__import__(user_input)

importlib.import_module(user_input)
```

Dynamic imports for plugins must also follow:

```text
docs/agent-guardrails/50-plugin-standards.md
docs/agent-guardrails/60-security-and-risk.md
```

---

## Logging

Use Loguru for application logging.

Do not use `print()` for normal diagnostics, progress messages, warning
messages, or errors.

Good:

```python
from loguru import logger


def process_file(path: Path) -> None:
    """Process a file.

    Args:
        path (Path): File to process.
    """
    logger.info("Processing file: {}", path)
```

Bad:

```python
print(f"Processing file: {path}")
```

Logging rules:

- Use structured message arguments where practical.
- Do not log passwords, tokens, keys, wallets, cookies, or secrets.
- Do not log complete configuration objects.
- Do not log large CLOB-like payloads unless explicitly needed.
- Log enough to diagnose failures.
- Avoid noisy logs that obscure useful information.
- Prefer clear action/result messages.

Good:

```python
logger.debug(
    "Loaded plugin {} with {} declared capabilities",
    plugin_id,
    capability_count,
)
```

Bad:

```python
logger.debug("Config: {}", config_mgr)
```

---

## Naming

Use these naming conventions:

| Item | Convention | Example |
|---|---|---|
| Package | `lower_with_underscores` | `orac_plugins` |
| Module | `lower_with_underscores` | `plugin_runtime` |
| Function | `lower_with_underscores` | `load_plugin` |
| Variable | `lower_with_underscores` | `plugin_id` |
| Class | `CapWords` | `PluginRegistry` |
| Exception | `CapWords` | `PluginLoadError` |
| Constant | `UPPER_CASE` | `DEFAULT_TIMEOUT` |
| Protected member | `_leading_underscore` | `_load_manifest` |

Avoid single-letter names except for trivial loops or conventional
mathematical notation.

Do not use double underscore names unless implementing Python protocol
methods such as `__init__`.

---

## Whitespace

Rules:

- Use spaces around binary operators.
- Do not over-pad expressions.
- Use spaces after commas.
- Do not add spaces inside brackets.
- Do not leave trailing whitespace.
- Use blank lines to group logical sections.

Good:

```python
total = a + b
coords = (x, y)
scores[index] = min(scores[index] + 1, 10)
```

Bad:

```python
total=a+b
coords = ( x, y )
scores[index]=min(scores[index]+1,10)
```

Function calls:

```python
result = calculate_total(price=price, quantity=quantity)
```

Slices:

```python
selected = values[start:stop:step]
```

---

## Expressions and statements

Use truthiness naturally.

Good:

```python
if items:
    process_items(items=items)
```

Bad:

```python
if len(items) != 0:
    process_items(items=items)
```

Use `is None` and `is not None`.

Good:

```python
if result is None:
    return None
```

Bad:

```python
if result == None:
    return None
```

Do not compare booleans to `True` or `False`.

Good:

```python
if enabled:
    start_service()
```

Bad:

```python
if enabled is True:
    start_service()
```

Use ternary expressions only for simple cases.

Good:

```python
label = "enabled" if enabled else "disabled"
```

Bad:

```python
result = run_a() if complex_condition() and check_b() else run_c()
```

---

## Functions

Prefer small, focused functions.

Complexity guideline:

| Function length | Guidance |
|---|---|
| Up to 20 lines | Ideal |
| 21 to 40 lines | Acceptable with clear structure |
| More than 40 lines | Refactor or explain why not |

These counts exclude:

- docstrings
- blank lines
- comments

Rules:

- Use clear function names.
- Keep parameter lists short where possible.
- Put defaulted parameters after required parameters.
- Use keyword-only arguments where clarity helps.
- Avoid boolean flag arguments that make functions do unrelated things.
- Return explicit values.
- Avoid hidden mutation unless the function name makes it clear.

---

## Mutable defaults

Do not use mutable default argument values.

Bad:

```python
def add_item(item: str, bag: list[str] = []) -> list[str]:
    bag.append(item)
    return bag
```

Good:

```python
def add_item(item: str, bag: list[str] | None = None) -> list[str]:
    """Add an item to a bag.

    Args:
        item (str): Item to add.
        bag (list[str] | None): Existing bag, or None to create a new
            one.

    Returns:
        list[str]: Bag containing the new item.
    """
    if bag is None:
        bag = []

    bag.append(item)
    return bag
```

Use a sentinel object when `None` is a meaningful value.

---

## Docstrings

Use Google-style docstrings by default.

Use triple double quotes.

The first line must be a short summary.

Include sections as needed:

- `Args`
- `Returns`
- `Raises`
- `Yields`

Do not document obvious implementation details.

Document purpose, constraints, side effects, and important error cases.

Good:

```python
def connect(host: str, port: int, timeout: int | None = None) -> None:
    """Connect to a server.

    Args:
        host (str): Hostname or IP address.
        port (int): TCP port number.
        timeout (int | None): Timeout in seconds, or None for no
            timeout.

    Raises:
        ConnectionError: If the server cannot be reached.
    """
```

Class docstring:

```python
class DBSession:
    """Manage a database session lifecycle.

    Handles connection setup, retries, and cleanup.

    Args:
        dsn (str): Data source name.
        autocommit (bool): Whether to enable autocommit.
    """
```

Method docstring:

```python
class DBSession:
    """Manage a database session lifecycle."""

    def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            RuntimeError: If no active transaction exists.
        """
```

---

## NumPy-style docstrings

Use NumPy-style docstrings only where explicitly appropriate for data
science or numerical code.

Example:

```python
def add(a: int, b: int) -> int:
    """Add two integers.

    Parameters
    ----------
    a : int
        First integer.
    b : int
        Second integer.

    Returns
    -------
    int
        The sum of ``a`` and ``b``.
    """
    return a + b
```

Do not mix Google style and NumPy style in the same module unless there
is a strong reason.

---

## Comments

Comments should explain why, not merely what.

Good:

```python
# The weather API sometimes returns duplicate location matches, so keep
# the first exact country match before falling back to score order.
```

Bad:

```python
# Loop over locations.
for location in locations:
    ...
```

Rules:

- Keep comments up to date.
- Remove comments that no longer match the code.
- Avoid commented-out code.
- Use inline comments sparingly.
- Put two spaces before an inline comment.

Example:

```python
timeout = 10  # Weather API occasionally stalls on DNS lookup.
```

---

## Command line interfaces

Any Python program intended to be used as a command line interface must
use `argparse`.

Do not parse `sys.argv` manually except in unusual, explicitly justified
cases.

Use this structure:

- `build_parser()`
- `main()`
- `if __name__ == "__main__"`

Example:

```python
import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="orac-tool",
        description="Process input and write a report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input file path, or '-' for stdin.",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        metavar="PATH",
        help="Path to YAML configuration file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="Write results to FILE.",
    )

    parser.add_argument(
        "--log-level",
        choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level. Default: %(default)s.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity. Use -v or -vv.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of records to process.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="orac-tool 1.0.0",
        help="Show version and exit.",
    )

    return parser


def main() -> int:
    """Run the command line program.

    Returns:
        int: Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than 0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Typing policy

Use type hints for:

- public functions
- public methods
- important private helpers
- class attributes where useful
- module constants where useful

Core rule:

```text
Accept the weakest thing you need.
Return the strongest thing you promise.
```

This means:

- use abstract collection types for inputs
- use concrete collection types for outputs

Import collection protocols from `collections.abc`.

```python
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import MutableMapping
from collections.abc import MutableSequence
from collections.abc import Sequence
from collections.abc import Set
```

Use modern Python syntax:

```python
list[str]
dict[str, int]
str | None
```

Prefer this:

```python
def normalise(names: Iterable[str]) -> list[str]:
    """Normalise names.

    Args:
        names (Iterable[str]): Names to normalise.

    Returns:
        list[str]: Normalised names.
    """
    return [name.strip().lower() for name in names]
```

Avoid this for input-only collections:

```python
def normalise(names: list[str]) -> list[str]:
    ...
```

Unless the function genuinely requires a list.

---

## Typing scalars

Use these scalar types:

| Purpose | Type |
|---|---|
| Counts and indexes | `int` |
| Approximate maths | `float` |
| Money | `decimal.Decimal` |
| Booleans | `bool` |
| Text | `str` |
| Binary data | `bytes` or `bytearray` |
| Paths | `pathlib.Path` |
| Durations | `datetime.timedelta` |
| Strong identifiers | `uuid.UUID`, `Enum`, or `Literal` |

Use timezone-aware datetimes where time zones matter.

Prefer UTC for persisted or cross-system timestamps.

Use `Final` for constants where useful:

```python
from typing import Final

MAX_RETRIES: Final[int] = 5
```

---

## Typing containers

Use these input types:

| Situation | Input type |
|---|---|
| You only iterate | `Iterable[T]` |
| Need length or membership | `Collection[T]` |
| Need indexing or order, no mutation | `Sequence[T]` |
| Need in-place sequence mutation | `MutableSequence[T]` |
| Need read-only dict-like access | `Mapping[K, V]` |
| Need dict-like mutation | `MutableMapping[K, V]` |
| Need set semantics | `Set[T]` |

Use these return types:

| Situation | Return type |
|---|---|
| Ordered mutable collection | `list[T]` |
| Ordered immutable collection | `tuple[T, ...]` |
| Mapping created by the function | `dict[K, V]` |
| Set created by the function | `set[T]` or `frozenset[T]` |

Examples:

```python
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import MutableMapping
from collections.abc import Sequence


def normalise(names: Iterable[str]) -> list[str]:
    """Normalise names."""
    return [name.strip().lower() for name in names]


def top3(scores: Sequence[float]) -> tuple[float, float, float]:
    """Return the top three scores."""
    ordered = sorted(scores, reverse=True)
    return ordered[0], ordered[1], ordered[2]


def render(context: Mapping[str, str]) -> str:
    """Render a context mapping."""
    return "\n".join(f"{key}: {value}" for key, value in context.items())


def ensure_default(
    values: MutableMapping[str, int],
    key: str,
    default: int = 0,
) -> int:
    """Ensure a mapping has a default value for a key."""
    return values.setdefault(key, default)
```

---

## Iterators and callables

Use `Iterator[T]` only for one-shot streams that are yielded.

Use `Callable` with explicit signatures.

Examples:

```python
from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path


def lines(path: Path) -> Iterator[str]:
    """Yield lines from a file.

    Args:
        path (Path): File path.

    Yields:
        str: One line at a time.
    """
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            yield line.rstrip("\n")


def retry(fn: Callable[[], None], attempts: int = 3) -> None:
    """Retry a callable.

    Args:
        fn (Callable[[], None]): Callable to execute.
        attempts (int): Number of attempts.

    Raises:
        ValueError: If attempts is less than 1.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(attempts):
        try:
            fn()
            return
        except Exception:
            if attempt == attempts - 1:
                raise
```

---

## Constants

Avoid magic literals in core logic.

Use constants for values with meaning.

Good:

```python
DEFAULT_TIMEOUT_SECONDS = 10
MAX_PLUGIN_RESULTS = 20
```

Bad:

```python
response = client.get(url, timeout=10)
```

Constants used only inside one function may be local constants.

Constants used across a module should be declared near the top of the
module.

Constants used across modules should live in an appropriate shared
module.

---

## Exceptions

Use specific exceptions.

Create project-specific exceptions where useful.

Do not catch broad exceptions unless you are adding context, logging, or
converting to a safer public error.

If catching `Exception`, re-raise unless there is a deliberate recovery
path.

Good:

```python
class PluginLoadError(RuntimeError):
    """Raised when a plugin cannot be loaded."""


def load_plugin(plugin_id: str) -> object:
    """Load a plugin.

    Args:
        plugin_id (str): Plugin identifier.

    Returns:
        object: Loaded plugin provider.

    Raises:
        PluginLoadError: If the plugin cannot be loaded.
    """
    try:
        return load_plugin_module(plugin_id=plugin_id)
    except ImportError as exc:
        raise PluginLoadError(
            f"Unable to load plugin provider for {plugin_id}"
        ) from exc
```

Bad:

```python
try:
    return load_plugin_module(plugin_id)
except Exception:
    return None
```

---

## Files and paths

Use `pathlib.Path`.

Good:

```python
from pathlib import Path


def read_text(path: Path) -> str:
    """Read a text file.

    Args:
        path (Path): File path.

    Returns:
        str: File content.
    """
    return path.read_text(encoding="utf-8")
```

Bad:

```python
def read_text(path: str) -> str:
    with open(path) as f:
        return f.read()
```

Use explicit encodings for text files.

Prefer UTF-8.

---

## Configuration

Do not pass broad configuration managers into components that only need
a narrow subset of configuration.

For plugin code, prefer a narrow plugin context object.

Good:

```python
@dataclass(frozen=True)
class PluginContext:
    """Runtime context passed to a plugin.

    Args:
        plugin_id (str): Plugin identifier.
        config (Mapping[str, object]): Plugin-specific configuration.
        correlation_id (str): Correlation id for logging.
    """

    plugin_id: str
    config: Mapping[str, object]
    correlation_id: str
```

Avoid passing full application managers to plugins unless explicitly
justified.

Bad:

```python
plugin.run(config_mgr=config_mgr)
```

---

## Security-sensitive Python

Python code that touches security-sensitive areas must follow:

```text
docs/agent-guardrails/60-security-and-risk.md
```

Security-sensitive areas include:

- dynamic imports
- plugin loading
- plugin execution
- credentials
- external network calls
- filesystem access
- shell command execution
- SQL execution
- context assembly
- message persistence
- home automation control

Rules:

- Do not use `shell=True` unless explicitly approved.
- Do not pass raw LLM output to a shell.
- Do not pass raw LLM output to SQL.
- Do not log secrets.
- Do not expose secrets to plugins unnecessarily.
- Do not expose secrets to the LLM.
- Validate inputs at trust boundaries.
- Fail closed when policy cannot be evaluated.

---

## Subprocesses

Avoid subprocess execution unless there is a clear need.

Prefer Python APIs over shell commands.

If subprocess execution is required:

- pass arguments as a list
- avoid `shell=True`
- set a timeout
- capture output deliberately
- log safe command summaries only
- validate all user-supplied arguments

Good:

```python
import subprocess


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command safely.

    Args:
        command (list[str]): Command and arguments.

    Returns:
        subprocess.CompletedProcess[str]: Completed process result.
    """
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
```

Bad:

```python
subprocess.run(user_supplied_command, shell=True)
```

---

## Tests

Python changes should include tests where practical.

Tests should cover:

- normal success paths
- invalid input
- missing files
- missing optional dependencies
- plugin load failures
- disabled plugin behaviour
- permission denial paths
- error handling
- logging safety where relevant

Do not test only the happy path.

For plugin-related tests, also follow:

```text
docs/agent-guardrails/50-plugin-standards.md
```

For security-sensitive tests, also follow:

```text
docs/agent-guardrails/60-security-and-risk.md
```

---

## Agent rules

When generating or modifying Python code, agents must:

1. Follow this document.
2. Preserve existing working patterns unless asked to refactor.
3. Use 4-space indentation for Python.
4. Add type hints for public functions and methods.
5. Use Google-style docstrings unless a file clearly uses NumPy style.
6. Use `argparse` for command line interfaces.
7. Use Loguru for logging.
8. Avoid `print()` for diagnostics.
9. Avoid wildcard imports.
10. Avoid ad hoc dynamic imports.
11. Keep plugin dynamic imports centralised in the plugin runtime.
12. Validate plugin identifiers before import.
13. Avoid broad configuration access in plugins.
14. Avoid logging secrets.
15. Add tests for meaningful behaviour changes.
16. Do not weaken security or plugin guardrails for convenience.

---

## Quick do and don't

| Situation | Do | Don't |
|---|---|---|
| CLI arguments | `argparse` | manual `sys.argv` parsing |
| Logging | Loguru | `print()` |
| Normal imports | static imports | scattered dynamic imports |
| Plugin loading | central `importlib` loader | `exec`, `eval`, raw user input |
| Input you only loop over | `Iterable[T]` | `list[T]` |
| Read-only indexed input | `Sequence[T]` | `list[T]` |
| Read-only mapping input | `Mapping[K, V]` | `dict[K, V]` |
| Mutable mapping input | `MutableMapping[K, V]` | `dict[K, V]` without reason |
| Return collection | `list[T]` or `tuple[T, ...]` | vague `Iterable[T]` |
| Money | `Decimal` | `float` |
| Paths | `Path` | `str` |
| Optional | `T | None` | `Optional[T]` in new code |
| Mutable defaults | `None` sentinel | `[]` or `{}` |
| Secrets | masked or omitted | raw values in logs |

---

## Final rule

Python code should be clear, typed, logged, testable, and safe.

Normal code should use ordinary static imports.

Only the plugin framework should use controlled dynamic imports.

Any code that makes plugin execution, filesystem access, SQL execution,
shell execution, or credential access easier by bypassing Orac guardrails
is a design defect.

