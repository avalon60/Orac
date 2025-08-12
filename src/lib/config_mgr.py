# src/controller/config_mgr.py
__author__ = "Clive Bostock"
__date__ = "2024-11-09"
__description__ = "Manages configuration via configparser with env/db overrides."

from __future__ import annotations
from pathlib import Path
from configparser import ConfigParser, ExtendedInterpolation
from typing import Iterable, Tuple, Optional, Dict, Any, List
import os

def _expand_path(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))

class ConfigManager:
    """
    Load an INI file with ExtendedInterpolation, then apply:
      1) environment overrides: ORAC__SECTION__KEY=value
      2) optional db overrides (apply_db_overrides())

    Search order (first that exists wins) if config_file_path is None:
      - resources/config/orac.ini
      - ~/.config/orac/orac.ini (XDG)
      - /etc/orac/orac.ini
    """

    def __init__(
        self,
        config_file_path: Optional[Path] = None,
        *,
        env_prefix: str = "ORAC__",
        search_paths: Optional[Iterable[Path]] = None,
    ):
        self.env_prefix = env_prefix
        self.search_paths: List[Path] = list(search_paths) if search_paths else [
            Path("resources/config/orac.ini"),
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "orac" / "orac.ini",
            Path("/etc/orac/orac.ini"),
        ]

        # Resolve config file
        if config_file_path is None:
            for cand in self.search_paths:
                if cand.exists():
                    config_file_path = cand
                    break
        if config_file_path is None:
            raise FileNotFoundError("No config file found in search paths.")
        self.config_file_path = Path(config_file_path)

        # Load
        self.config = ConfigParser(interpolation=ExtendedInterpolation())
        with open(self.config_file_path, encoding="utf-8") as f:
            self.config.read_file(f)

        # Apply environment overrides (ORAC__SECTION__KEY=value)
        self._apply_env_overrides()

        # Convenience: a flattened view (last one wins)
        self.global_substitutions: Dict[str, str] = {}
        self._hydrate_dictionary()

    # --------------------------- core helpers ---------------------------------
    def _apply_env_overrides(self) -> None:
        prefix = self.env_prefix
        for k, v in os.environ.items():
            if not k.startswith(prefix):
                continue
            try:
                _, section, key = k.split("__", 2)
            except ValueError:
                # ignore badly-formed keys
                continue
            section = section.lower()
            key = key.lower()
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, key, v)

    def _hydrate_dictionary(self) -> None:
        self.global_substitutions.clear()
        for section in self.config.sections():
            for key, val in self.config.items(section):
                self.global_substitutions[key] = val  # note: simple flatten, last one wins

    # --------------------------- typed getters --------------------------------
    def config_value(self, section: str, key: str, default: Optional[str] = None) -> str:
        if not self.config.has_section(section) or not self.config.has_option(section, key):
            if default is not None:
                return default
            raise KeyError(f"Missing config key {section}.{key} in {self.config_file_path}")
        return self.config.get(section, key)

    def bool_config_value(self, section: str, key: str, default: Optional[bool] = None) -> bool:
        if not self.config.has_section(section) or not self.config.has_option(section, key):
            if default is not None:
                return default
            raise KeyError(f"Missing config key {section}.{key} in {self.config_file_path}")
        return self.config.getboolean(section, key)

    def int_config_value(self, section: str, key: str, default: Optional[int] = None) -> int:
        if not self.config.has_section(section) or not self.config.has_option(section, key):
            if default is not None:
                return default
            raise KeyError(f"Missing config key {section}.{key} in {self.config_file_path}")
        return self.config.getint(section, key)

    def float_config_value(self, section: str, key: str, default: Optional[float] = None) -> float:
        if not self.config.has_section(section) or not self.config.has_option(section, key):
            if default is not None:
                return default
            raise KeyError(f"Missing config key {section}.{key} in {self.config_file_path}")
        return self.config.getfloat(section, key)

    def path_config_value(
        self, section: str, key: str, default: Optional[str] = None, suppress_warnings: bool = False
    ) -> Path:
        raw = self.config_value(section, key, default=default)
        expanded = _expand_path(raw)
        # warn if it doesn't look like a path (optional)
        if not suppress_warnings and not (os.path.isabs(expanded) or any(sep in expanded for sep in ("/", "\\"))):
            print(f"WARNING: expected a path for {section}.{key}, got '{raw}'")
        return Path(expanded)

    def list_config_value(self, section: str, key: str, default: Optional[str] = None, sep: str = ",") -> List[str]:
        val = self.config_value(section, key, default=default)
        return [item.strip() for item in val.split(sep) if item.strip()]

    # --------------------------- overrides ------------------------------------
    def apply_db_overrides(self, kv_triples: Iterable[Tuple[str, str, Any]]) -> None:
        """
        Apply overrides from the database. Expects an iterable of (section, key, value).
        """
        for section, key, value in kv_triples:
            s = section.lower()
            k = key.lower()
            if not self.config.has_section(s):
                self.config.add_section(s)
            self.config.set(s, k, str(value))
        self._hydrate_dictionary()

    # --------------------------- misc -----------------------------------------
    def section_dict(self, section: str) -> Dict[str, str]:
        if not self.config.has_section(section):
            return {}
        return {k: v for k, v in self.config.items(section)}

    def config_dictionary(self) -> Dict[str, str]:
        return dict(self.global_substitutions)

    def print_config(self) -> None:
        print(f"*** Config ({self.config_file_path}) ***")
        for section in self.config.sections():
            print(f"\n[{section}]")
            for k, v in self.config.items(section):
                print(f"{k} = {v}")
        print("\n*** End of Config ***")

    def banner(self) -> str:
        """Return a one-liner summarising key settings for startup logs."""
        svc = self.config.get("service", "llm_service_id", fallback="n/a")
        model = self.config.get("service", "default_model_name", fallback="n/a")
        url = self.config.get("service", "service_url", fallback="n/a")
        gran = self.config.get("vector_db", "granularity", fallback="chunk_3")
        return f"config: service={svc} model={model} url={url} vector.granularity={gran}"

    def __repr__(self) -> str:
        return f"<ConfigManager(config_file_path='{self.config_file_path}')>"

if __name__ == "__main__":

    # Example: load from default search paths
    cm = ConfigManager()
    cm.print_config()
    print(cm.banner())

