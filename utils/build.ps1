<#
.SYNOPSIS
    Performs a build and install of the project as packages.

.DESCRIPTION
    PowerShell port of build.sh by Clive Bostock
    Author: Clive Bostock
    Date: 16 Dec 2024
#>

# Get full path to this script
$ScriptPath = $MyInvocation.MyCommand.Path
$ScriptDir = Split-Path -Path $ScriptPath -Parent
$AppHome = Split-Path -Path $ScriptDir -Parent

Push-Location $AppHome

# Source the PowerShell environment functions
. "$AppHome\utils\utils.env.ps1"

# Call setup functions
Set-Python
Ensure-Pip

# Determine the virtual environment directory
$VenvDir = Join-Path -Path $AppHome -ChildPath ".venv"
if (-Not (Test-Path $VenvDir)) {
    & $Global:PYTHON -m venv $VenvDir
}

Write-Output "App home: $AppHome"

# Activate the virtual environment
$activateScript = Join-Path -Path $VenvDir -ChildPath "Scripts\Activate.ps1"
. $activateScript

# Install the BDDS framework
& $Global:PYTHON -m pip install .

