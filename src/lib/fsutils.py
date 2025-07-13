__author__ = "Clive Bostock"
__date__ = "2024-11-09"
__description__ = "Manages the database connection/close."

import re
import os
import platform
from pathlib import Path
import shutil
from typing import Optional

# Get the real path of the current script
real_path = Path(__file__).resolve()

# We assume that our project is based on the <project-root>/src/package paradigm.
# Traverse back based on the known project structure.
project_home_dir = real_path
while project_home_dir.name != "src" and project_home_dir != project_home_dir.parent:
    project_home_dir = project_home_dir.parent
    # Make sure we get the parent of the `src` directory
    if project_home_dir.name == "src" or project_home_dir.name in ('venv', '.venv'):
        project_home_dir = project_home_dir.parent
        break


def project_home() -> Path:
    # We have the option of overriding the project home with a shell variable.
    # This mechanism is used by BDDS Orchestrator to broadcast the staging area
    # project home.
    bdds_project_home = os.environ.get("BDDS_PROJECT_HOME")
    if bdds_project_home is not None:
        return Path(bdds_project_home)
    else:
        return project_home_dir


def find_highest_release(directory: Path, file_prefix: str = 'bdds') -> Optional[Path]:
    """Find the highest versioned file in a directory matching the format
    '<file_prefix>-x.y.z.tar.gz'. E.g. bdds-2.3.1.tar.gz.

    Args:
        directory (Path): The directory to search for matching files.
        file_prefix (str): The expected filename prefix (e.g. 'bdds').

    Returns:
        Optional[Path]: Path to the file with the highest version number,
                        or None if no matching file is found.
    """
    # Escape prefix in case it contains regex meta characters
    escaped_prefix = re.escape(file_prefix)
    pattern = re.compile(rf"^{escaped_prefix}-(\d+)\.(\d+)\.(\d+)\.tar\.gz$")

    highest_version = (-1, -1, -1)
    selected_file = None

    for file in directory.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                version = tuple(map(int, match.groups()))
                if version > highest_version:
                    highest_version = version
                    selected_file = file

    return selected_file


def is_valid_dir_name(directory_name: str) -> bool:
    """
    Checks if a string is a valid directory name for the current operating system.

    :param directory_name: The input string to check.
    :type directory_name: str
    :return: True if the string is valid, False otherwise.
    :rtype: bool
    """
    # Determine the invalid characters based on the OS
    if platform.system() == "Windows":
        # Windows restrictions: \ / : * ? " < > |
        invalid_pattern = r'[\\/:*?"<>|]'
    else:
        # Unix-like systems restrictions: /
        invalid_pattern = r'[\/]'

    # Check for invalid characters
    if re.search(invalid_pattern, directory_name):
        return False

    # Optional: Ensure it's not empty or just whitespace
    if not directory_name.strip():
        return False

    return True


def sanitise_dir_name(directory_name: str) -> str:
    """
    Sanitises a string to make it a valid directory name by removing invalid characters.

    :param directory_name: The input string to sanitise.
    :type directory_name: str
    :return: A sanitised directory name.
    :rtype: str
    """
    # Determine the invalid characters based on the OS

    # invalid_chars = r'[\/]'       # Linux
    invalid_chars = r'[\\/:*?"<>|]'  # We adopt Windows invalid characters

    # Replace invalid characters with an underscore or another safe character
    sanitised_name = re.sub(invalid_chars, '', directory_name)

    # Remove any leading or trailing whitespace
    sanitised_name = sanitised_name.strip()

    # Optional: Ensure the directory name is not empty after sanitisation
    if not sanitised_name:
        raise ValueError("The directory name is empty after sanitisation.")

    return sanitised_name


def zip_directory(zip_source_dir: Path, zip_file_name, destination_dir: Path = None):
    """Zips a directory and its contents into a zip file. If a destination_dir is provided, the generated zip file is
    relocated to destination_dir.

      :param zip_source_dir: The path to the directory to zip.
      :type zip_source_dir: Path
      :param zip_file_name: The path to the output zip file.
      :type zip_file_name: str
      :param destination_dir: The place to locate the generated zip file.
      :type destination_dir:
    """

    # The make_archive method automatically adds a .zip extension. So we remove it.
    _zip_file = zip_file_name.replace('.zip', '')
    shutil.make_archive(_zip_file, 'zip', zip_source_dir)

    if destination_dir:
        if not destination_dir.exists():
            destination_dir.mkdir()
        shutil.move(_zip_file + '.zip', destination_dir)


if __name__ == "__main__":
    dir_name = r'?[abc\/?'
    sanitised_dir_name = sanitise_dir_name(directory_name=dir_name)
    print(f"sanitised directory name: {sanitised_dir_name}")
    print(f'Project Home: {project_home()}')
