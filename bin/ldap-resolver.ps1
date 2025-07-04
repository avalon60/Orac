<#
------------------------------------------------------------------------------
 Author: Clive Bostock
   Date: 03 July 2025
   Name: ldap-resolver.ps1 (LDAP Resolver tool - LDAP Alias -> connect string)
  Descr: Wrapper PowerShell script for calling  ldap-resolver.py
------------------------------------------------------------------------------
#>

function Get-RealPath {
    param (
        [string]$Path
    )
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    } else {
        return (Resolve-Path -Path $Path).Path
    }
}

# Determine script location
$ScriptPath   = $MyInvocation.MyCommand.Path
$ScriptDir    = Split-Path -Parent (Get-RealPath $ScriptPath)
$ProjectDir   = Split-Path -Parent $ScriptDir
$ControlDir   = Join-Path $ProjectDir 'src/controller'
$ScriptName   = [System.IO.Path]::GetFileNameWithoutExtension($ScriptPath)
$EntryPoint   = "$ScriptName.py"

# Virtual environment setup
$VenvDir      = Join-Path $ProjectDir '.venv'
$VenvScriptsDir = Get-ChildItem -Path $VenvDir -Directory -Filter 'Scripts' `
    | Select-Object -ExpandProperty FullName -ErrorAction SilentlyContinue

if (-not $VenvScriptsDir) {
    $VenvScriptsDir = Join-Path $VenvDir 'Scripts'
}

$ActivateScript = Join-Path $VenvScriptsDir 'Activate.ps1'

# Check if virtual environment is already active
if ($env:VIRTUAL_ENV) {
    Write-Host 'Virtual environment already activated.'
}
elseif (Test-Path $ActivateScript) {
    if ((Get-ExecutionPolicy) -eq 'Restricted') {
        Write-Host 'WARNING: PowerShell script execution is restricted. Run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass'
        exit 1
    }
    Write-Host 'Activating virtual environment...'
    try {
        & $ActivateScript
    }
    catch {
        Write-Host 'WARNING: Failed to activate virtual environment.'
    }
}
else {
    Write-Host 'WARNING: Unable to locate a venv directory or activate script; proceeding without virtual environment.'
}

# Determine the Python interpreter
$PYTHON_INTERPRETER = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PYTHON_INTERPRETER = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PYTHON_INTERPRETER = "py"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $PYTHON_INTERPRETER = "python3"
}

# Error handling if no interpreter found
if (-not $PYTHON_INTERPRETER) {
    Write-Error "Error: No compatible Python interpreter found (python3, python, or py)!"
    exit 1
}

# Execute the Python program
Write-Host "Executing Python script..."
& $PYTHON_INTERPRETER (Join-Path $ControlDir $EntryPoint) @Args
