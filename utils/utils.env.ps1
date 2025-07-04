#------------------------------------------------------------------------------
# Author: Clive Bostock
#   Date: 16 February 2025
#   Name: utils.env.ps1
#
#  Descr: Sourcing script for setting up utility environment variables and functions.
#         Intended for installation activities like determining Python interpreter,
#         virtual environment activation, and pip setup.
#------------------------------------------------------------------------------

function Get-VenvDir {
    if (-not $env:VENV_DIR) {
        if (Test-Path "venv") {
            $env:VENV_DIR = "venv"
        } elseif (Test-Path ".venv") {
            $env:VENV_DIR = ".venv"
        } else {
            Write-Error "Cannot locate the Python virtual environment directory!"
            exit 1
        }
    }
}

function Source-Venv {
    Get-VenvDir

    $binPathUnix = Join-Path $env:VENV_DIR "bin\activate.ps1"
    $binPathWin = Join-Path $env:VENV_DIR "Scripts\Activate.ps1"

    if (Test-Path $binPathUnix) {
        . $binPathUnix
    } elseif (Test-Path $binPathWin) {
        . $binPathWin
    } else {
        Write-Error "Cannot locate activate script in venv directory!"
        exit 1
    }
}

function Set-Python {
    if ($env:OS -eq "Windows_NT") {
        $Global:PYTHON = "python.exe"
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $Global:PYTHON = "python3"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Global:PYTHON = "python"
    } else {
        Write-Error "Python is not installed."
        exit 1
    }

    Write-Output "Using Python interpreter: $Global:PYTHON"
}


function Ensure-Pip {
    if (-not (Get-Command pip -ErrorAction SilentlyContinue)) {
        Write-Host "pip not found. Installing pip..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"
        & $PYTHON get-pip.py
        Remove-Item "get-pip.py"
    } else {
        Write-Host "pip is already installed."
    }
}

