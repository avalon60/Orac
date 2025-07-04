#------------------------------------------------------------------------------
# Author: Clive Bostock
#   Date: 16 February 2025
#   Name: utils.ps1
#
#  Descr: Sourcing (dot-sourcing utils.ps1) script to set up the utilities 
#         environment variables and functions. These are mainly oriented around 
#         installation type activities, such as determining whether Python is 
#         installed, what the Python interpreter command is, ensuring PIP is 
#         installed, etc.
#------------------------------------------------------------------------------
# Function to determine which virtual environment directory is being used
function venv_dir {
    if (Test-Path "venv") {
        $global:VENV_DIR = "venv"
    } elseif (Test-Path ".venv") {
        $global:VENV_DIR = ".venv"
    } else {
        Write-Error "Cannot locate the Python virtual environment directory!"
        exit 1
    }
}

# Function to source (activate) the virtual environment
function source_venv {
    venv_dir
    if (Test-Path "$VENV_DIR/bin/activate") {
        . "$VENV_DIR/bin/activate"
    } elseif (Test-Path "$VENV_DIR/Scripts/Activate.ps1") {
        & "$VENV_DIR/Scripts/Activate.ps1"
    } else {
        Write-Error "Cannot locate activate script from venv directory!"
        exit 1
    }
}

# Function to determine the Python interpreter
function set_python {
    if ($env:OS -eq "Windows_NT") {
        $global:PYTHON = "python"
        $global:SOURCE_DIR = "Scripts"
    } elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
        $global:PYTHON = "python3"
        $global:SOURCE_DIR = "bin"
    } else {
        Write-Error "Error: Python interpreter not found."
        exit 1
    }

    try {
        & $PYTHON --version
        Write-Output "Using Python interpreter: $PYTHON"
    } catch {
        Write-Error "Error: Neither python3 nor python is installed."
        exit 1
    }
}

# Function to ensure pip is installed
function ensure_pip {
    if (!(Get-Command "pip" -ErrorAction SilentlyContinue)) {
        Write-Output "pip not found. Installing pip..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"
        & $PYTHON "get-pip.py"
        Remove-Item "get-pip.py"
    } else {
        Write-Output "pip is already installed."
    }
}

