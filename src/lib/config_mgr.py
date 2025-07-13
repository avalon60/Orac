__author__ = "Clive Bostock"
__date__ = "2024-11-09"
__description__ = "Manages the configuration data via configparser."

from pathlib import Path
from configparser import ExtendedInterpolation
import configparser
import os


class ConfigManager:
    def __init__(self, config_file_path: Path):
        self.config_file_path = Path(config_file_path)
        self.check_for_config_file()
        self.config = configparser.ConfigParser(interpolation=ExtendedInterpolation())
        with open(self.config_file_path, encoding="utf-8") as f:
            self.config.read_file(f)
        self.global_substitutions = {}
        self._hydrate_dictionary()

    def check_for_config_file(self) -> None:
        """Check if the config file exists. Raise FileNotFoundError if missing."""
        if not self.config_file_path.exists():
            print(f'Unable to locate the config file: {self.config_file_path}')
            raise FileNotFoundError

    def config_value(self, config_section: str, config_key: str, default: str = None) -> str:
        """
        Retrieve a value from the config file and strip whitespace.

        :param config_section: Section of the config file.
        :param config_key: Key to retrieve.
        :param default: Default if key is not found.
        :return: Trimmed string value from the config.
        """
        if not self.config.has_option(config_section, config_key) and default is not None:
            return default.strip() if isinstance(default, str) else default

        if not self.config.has_section(config_section) or not self.config.has_option(config_section, config_key):
            message = f"The key {config_section}.{config_key} does not exist in the config file ({self.config_file_path})."
            raise KeyError(message)

        # Return value with leading/trailing whitespace removed
        return self.config.get(config_section, config_key).strip()

    def bool_config_value(self, config_section: str, config_key: str, default: bool = None) -> bool:
        """
        Retrieve a boolean value from the config file.

        :param config_section: Section of the config file.
        :param config_key: Key to retrieve.
        :param default: Default if key is not found.
        :return: Boolean value from the config.
        """
        if not self.config.has_option(config_section, config_key) and default is not None:
            return default

        if not self.config.has_section(config_section) or not self.config.has_option(config_section, config_key):
            message = f"The key {config_section}.{config_key} does not exist in the config file ({self.config_file_path})."
            raise KeyError(message)

        return self.config.getboolean(section=config_section, option=config_key)

    def config_dictionary(self):
        """Return the full config as a flat dictionary."""
        return self.global_substitutions

    def _hydrate_dictionary(self):
        """Populate global_substitutions from all config sections."""
        for section in self.config.sections():
            # Strip whitespace from values before storing
            self.global_substitutions.update({
                k: v.strip() if isinstance(v, str) else v
                for k, v in self.config.items(section)
            })

    def path_config_value(self, config_section: str, config_key: str,
                          default: str = None, suppress_warnings: bool = False) -> Path:
        """
        Retrieve a value as a Path object, trimming whitespace.

        :param config_section: Section of the config file.
        :param config_key: Key to retrieve.
        :param default: Default if key is not found.
        :param suppress_warnings: Suppress path warnings.
        :return: Path object.
        """
        path_name = self.config_value(config_section=config_section, config_key=config_key, default=default)

        if not os.path.isabs(path_name) and ('/' not in path_name and '\\' not in path_name) and not suppress_warnings:
            print(
                f"WARNING: Expected a pathname from config_section: {config_section} / config_key: {config_key}, but "
                f"got '{path_name}'"
            )

        return Path(path_name)

    def print_config(self):
        """Print the entire contents of the config file."""
        print('*** Config Listing ***')
        for section in self.config.sections():
            print(f'\nSection: {section}')
            for property_name, property_value in self.config.items(section):
                print(f'  {property_name} = {property_value.strip()}')
        print('\n*** End of Config ***')

    def __repr__(self) -> str:
        """Return a string representation of the ConfigManager instance."""
        return f"<ConfigManager(config_file_path='{self.config_file_path}')>"


if __name__ == '__main__':
    config_file = Path('../../resources/config/samples/OraTAPI.ini.sample')
    config_manager = ConfigManager(config_file_path=config_file)
    config_manager.print_config()
