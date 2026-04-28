# Author: Clive Bostock

# Date: 2026-03-13

# Description: PowerShell launcher for split_ddl.py. Locates the Python

# script in the same directory and forwards all parameters.

param(
[Parameter(ValueFromRemainingArguments=$true)]
[string[]]$Args
)

# Directory where this .ps1 file resides

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Python script located beside this launcher

$pythonScript = Join-Path $scriptDir "split_ddl.py"

if (-not (Test-Path $pythonScript)) {
Write-Error "split_ddl.py not found beside launcher: $pythonScript"
exit 1
}

# Attempt to find Python

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCmd) {
Write-Error "Python interpreter not found in PATH."
exit 1
}

# Execute Python script with forwarded arguments

& python $pythonScript @Args

