<#
------------------------------------------------------------------------------
Author: Clive Bostock
Date: 16 December 2024
Name: setup.ps1
Descr: Script to set up the application environment, including creating a
       virtual environment, checking/installing pip, installing dependencies,
       and configuring scripts.
       Optionally unpacks Oracle Instant Client from zip file, flattening contents.
------------------------------------------------------------------------------
#>

param(
    [string]$ClientZip  # Optional path to Oracle Instant Client ZIP
)

# Set variables
$VENV_DIR = ".venv"
$step = 0
$PROG_PATH = $MyInvocation.MyCommand.Path
$APP_HOME = Split-Path -Parent $PROG_PATH
$BIN_DIR = "bin"
$UTILS_DIR = "utils"
$ORACLE_CLIENT_DIR = "oracle_client"

# Change to the application home directory
Push-Location $APP_HOME

# Step 0: Unpack Oracle Instant Client if zip path provided
if ($ClientZip) {
    Write-Output "Step 0: Unpacking Oracle Instant Client from: $ClientZip"

    if (!(Test-Path $ClientZip)) {
        Write-Error "Error: ZIP file not found: $ClientZip"
        Exit 1
    }

    if (Test-Path $ORACLE_CLIENT_DIR) {
        Remove-Item $ORACLE_CLIENT_DIR -Recurse -Force
    }
    New-Item -ItemType Directory -Path $ORACLE_CLIENT_DIR | Out-Null

    $TempPath = Join-Path $env:TEMP "ic_unzip_temp_$([guid]::NewGuid().ToString())"
    New-Item -ItemType Directory -Path $TempPath | Out-Null

    try {
        Expand-Archive -Path $ClientZip -DestinationPath $TempPath -Force

        $innerDir = Get-ChildItem $TempPath | Where-Object {
            $_.PSIsContainer -and $_.Name -like "instantclient_*"
        } | Select-Object -First 1

        if ($innerDir) {
            Write-Output "Flattening Instant Client files into: $ORACLE_CLIENT_DIR"
            Copy-Item -Path "$($innerDir.FullName)\*" -Destination $ORACLE_CLIENT_DIR -Recurse -Force
        } else {
            Write-Error "Error: Could not find 'instantclient_*' directory inside zip archive."
            Exit 1
        }

        Remove-Item -Recurse -Force $TempPath
        Write-Output "Instant Client successfully unpacked to: $ORACLE_CLIENT_DIR"
    } catch {
        Write-Error "Failed to extract Oracle Instant Client: $_"
        if (Test-Path $TempPath) {
            Remove-Item -Recurse -Force $TempPath
        }
        Exit 1
    }
}

# Determine Python interpreter
if ($env:OS -eq "Windows_NT") {
    $PYTHON = "python"
    $SOURCE_DIR = "Scripts"
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $PYTHON = "python3"
    $SOURCE_DIR = "bin"
} else {
    Write-Error "Error: Python interpreter not found."
    Exit 1
}

# Check if Python is installed
try {
    & $PYTHON --version
    Write-Output "Using Python interpreter: $PYTHON"
} catch {
    Write-Error "Error: Neither python3 nor python is installed."
    Exit 1
}

# Source utils.ps1
. .\utils\utils.ps1

# Step 1: Check if pip is installed
$step++
$step_desc = "Check if pip is installed"
Write-Output "Step ${step}: ${step_desc}..."
ensure_pip

# Step 2: Create virtual environment if it doesn't exist
$step++
$step_desc = "Create virtual environment if it doesn't exist"
Write-Output "Step ${step}: ${step_desc}..."
& $PYTHON -m venv $VENV_DIR
source_venv

# Step 3: Activate the virtual environment
$step++
$step_desc = "Activate the virtual environment"
Write-Output "Step ${step}: ${step_desc}..."
$VENV_PYTHON = Join-Path $APP_HOME "$VENV_DIR\$SOURCE_DIR\python.exe"
if (!(Test-Path $VENV_PYTHON)) {
    Write-Error "Error: Python not found in the virtual environment. Exiting."
    Exit 1
}
Write-Output "Activating virtual environment..."
& "$VENV_PYTHON" -m pip install --upgrade pip

# Step 4: Perform the packages install
$step++
$step_desc = "Perform the packages install"
Write-Output "Step ${step}: ${step_desc}..."
& "$VENV_PYTHON" -m pip install .

Write-Output "Setup completed successfully!"
Pop-Location

