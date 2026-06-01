# Bash Scripting Standards

## Purpose

This document defines standards for shell scripts.

Bash is the project standard shell scripting language for Linux, Windows WSL,
Windows Git Bash, and macOS. Shell scripts must be written as portable Bash
unless a task explicitly requires another shell.

The goals are:

- predictable behaviour across supported developer platforms
- low surprise for developers using Linux, WSL, Git Bash, or macOS
- safe filesystem handling
- readable command line tooling
- clear failure modes

Where these standards conflict with local project scripts that already exist,
preserve the existing working pattern unless explicitly asked to refactor it.

---

## Core rules

- Use Bash for shell scripts.
- Start executable Bash scripts with `#!/usr/bin/env bash`.
- Include the required script header immediately below the shebang.
- Use `set -euo pipefail` unless the script has a documented reason not to.
- Use functions for repeated or non-trivial logic.
- Keep functions small and name them for the action they perform.
- Quote variable expansions unless word splitting is explicitly required.
- Use arrays for argument lists where Bash arrays are appropriate.
- Use `local` for function-scoped variables.
- Prefer `printf` over `echo` for generated output.
- Send diagnostics and errors to stderr.
- Validate inputs before using them in filesystem, git, network, or destructive
  operations.
- Use `--` before path arguments for commands that support it.
- Do not assume GNU-only behaviour when macOS or Git Bash may run the script.

Example header:

```bash
#!/usr/bin/env bash
# Author: <login_id>
# Date: 22-May-2026
# Description: Demonstrates the required Bash script header.
set -euo pipefail
```

---

## File names and locations

Executable shell scripts should use the `.sh` file extension.

The main exception is a file intended to be sourced by another script. Sourced
files may omit `.sh` only when the local project convention already does so, or
when another extension such as `.bash` clearly communicates that the file is a
Bash library rather than a direct command.

Place shell scripts in a `scripts` or `bin` directory by default.

Use another location only when:

- an existing project convention already places that category of script
  elsewhere
- a tool or framework requires a specific path
- the script is intentionally local to a narrower subtree and the directory
  name makes that scope clear

Do not scatter one-off shell scripts across unrelated source directories.

---

## Supported platforms

Scripts must run under Bash on:

- Linux
- Windows WSL
- Windows Git Bash
- macOS

Do not depend on a platform-specific shell such as PowerShell, `cmd.exe`, or
`zsh` unless the script is explicitly scoped to that platform and documented as
such.

When platform-specific support is required, isolate it in a small function and
detect the available command at runtime.

---

## Portability rules

Use portable command forms by default.

Avoid relying on:

- GNU-only options without a fallback
- BSD-only options without a fallback
- Linux-only paths such as `/proc`
- WSL-only path behaviour
- Git Bash path conversion quirks
- commands that are not installed by default on macOS

Be especially careful with these commands and behaviours:

- `sed -i` differs between GNU `sed` and BSD/macOS `sed`; avoid in-place edits
  or provide a tested wrapper.
- `realpath` is absent from a default macOS install; prefer a helper based on
  `cd` and `pwd -P`, or provide a fallback.
- `readlink -f` is not portable to default macOS.
- `mktemp` syntax differs across platforms; use `mktemp -d` where possible and
  provide a fallback for constrained environments.
- `stat` options differ between GNU and BSD/macOS implementations.
- `date` formatting and parsing options differ between GNU and BSD/macOS
  implementations.
- `find` predicates and output formatting differ across implementations; keep
  usage simple.

If a script needs non-portable behaviour, document the reason and gate it behind
runtime detection.

---

## Paths and files

Treat paths as data.

- Quote all path variables.
- Avoid parsing `ls`.
- Do not build paths by assuming a trailing slash.
- Resolve directories with `cd -- "$path" && pwd -P` when a portable absolute
  directory path is needed.
- Resolve file paths by resolving the parent directory and appending the base
  name.
- Create parent directories before writing files.
- Validate computed delete or move targets before removing or moving them.
- Use `trap` cleanup for temporary directories and files.

Portable file absolute path helper:

```bash
absolute_path_for_file() {
  local path=$1
  local dir
  local base

  dir=$(dirname -- "$path")
  base=$(basename -- "$path")
  mkdir -p -- "$dir"
  dir=$(cd -- "$dir" && pwd -P)
  printf '%s/%s\n' "$dir" "$base"
}
```

---

## Text edits

Prefer generating a new file and moving it into place over in-place editing.

When editing text from Bash:

- Avoid `sed -i` unless the script provides a cross-platform wrapper.
- Use temporary files for multi-step transformations.
- Preserve line endings intentionally.
- Fail if the expected input pattern is absent and that absence would make the
  result ambiguous.
- Avoid ad hoc parsing when a structured parser is available.

If a script must use `sed`, keep expressions simple and test them under both
GNU and BSD/macOS `sed` behaviour.

---

## Command line interfaces

Use `getopts` for short options in simple Bash scripts.

For scripts with long options, subcommands, or complex validation, keep parsing
explicit and well tested. Do not hide complex CLI parsing in dense one-liners.

Every script intended for direct user invocation should provide:

- `-h` or `--help`
- clear usage text
- examples for common workflows
- actionable error messages

Reject unexpected positional arguments unless the script explicitly supports
them.

---

## Safety

Before running destructive or high-impact operations:

- validate the resolved target path
- confirm the path is inside the intended workspace or target repository
- require explicit confirmation when user data may be overwritten
- avoid recursive deletion unless the target has been checked

Do not use `eval` for command construction.

Do not execute strings derived from model output, user input, repository files,
or tool output unless they have been validated and constrained to an expected
command shape.

Do not log secrets or tokens.

---

## Testing

For material Bash changes, test at least:

- syntax with `bash -n`
- help output
- one successful common workflow
- one invalid input path or argument

When changing portability-sensitive logic, test or reason explicitly about
Linux, WSL, Git Bash, and macOS behaviour.
