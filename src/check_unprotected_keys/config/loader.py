"""Configuration loading for the scanner."""

from __future__ import annotations

import glob
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from check_unprotected_keys.config.models import ScanConfigSection
from check_unprotected_keys.domain.models import SearchConfiguration

# Safe default directories to never descend into when using broad bases.
# Users can extend via ignore_directories in their config (additive).
DEFAULT_IGNORE_DIRECTORIES: tuple[str, ...] = (
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "bower_components",
    ".venv",
    "venv",
    ".env",
    "env",
    "target",
    "dist",
    "build",
    "out",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "coverage",
    ".idea",
    ".vscode",
    ".vs",
    "tmp",
    "temp",
    ".tmp",
)

DEFAULT_CONFIG_FILENAME = ".check-unprotected-keys.toml"


class ConfigurationError(ValueError):
    """Raised when runtime scan configuration is missing or invalid."""


def read_example_configuration_text() -> str:
    """Return the packaged example configuration for installed users."""

    resource = files("check_unprotected_keys.resources").joinpath(
        "check-unprotected-keys.example.toml"
    )
    return resource.read_text(encoding="utf-8")


def load_search_configuration(
    execution_root: Path,
    *,
    config_filename: str = DEFAULT_CONFIG_FILENAME,
) -> SearchConfiguration:
    """Load and validate search configuration from the execution root."""

    root_path = execution_root.resolve()
    config_path = (root_path / config_filename).resolve()

    if not config_path.is_file():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}. "
            "Create .check-unprotected-keys.toml before running the scanner."
        )

    try:
        with config_path.open("rb") as file_obj:
            document = tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            f"Configuration file is not valid TOML: {config_path} ({exc})"
        ) from exc

    scan_table = document.get("scan")
    if not isinstance(scan_table, dict):
        raise ConfigurationError(
            "Configuration file must define a [scan] table with base_folders "
            "(or legacy folder_patterns) and filename_patterns."
        )

    # Determine base folders: prefer modern key, fall back to legacy for compat.
    if "base_folders" in scan_table:
        base_folders = _validate_patterns(scan_table, key="base_folders")
        legacy_used = False
    elif "folder_patterns" in scan_table:
        base_folders = _validate_patterns(scan_table, key="folder_patterns")
        legacy_used = True
    else:
        raise ConfigurationError(
            "scan.base_folders (or legacy scan.folder_patterns) must be "
            "a non-empty array."
        )

    # directory_names: explicit (may be empty to disable hints), or legacy
    # compat promotion of bare names from old folder_patterns lists.
    if "directory_names" in scan_table:
        directory_names = _validate_optional_patterns(scan_table, key="directory_names")
    elif legacy_used:
        # Auto-promote simple bare directory names from old-style folder_patterns
        # so users get broader discovery "for free" during transition.
        directory_names = tuple(
            p for p in base_folders if "/" not in p and not glob.has_magic(p)
        )
    else:
        directory_names = ()

    # ignore_directories: start with safe defaults, extend with user list
    # (user may provide empty list to drop all defaults).
    if "ignore_directories" in scan_table:
        user_ignores = _validate_optional_patterns(scan_table, key="ignore_directories")
        ignore_directories = tuple(
            dict.fromkeys(DEFAULT_IGNORE_DIRECTORIES + user_ignores)
        )
    else:
        ignore_directories = DEFAULT_IGNORE_DIRECTORIES

    filename_patterns = _validate_patterns(scan_table, key="filename_patterns")

    raw_limit = scan_table.get("max_directory_visits")
    if raw_limit is None:
        max_directory_visits = 100_000
    elif not isinstance(raw_limit, int) or raw_limit < 1:
        raise ConfigurationError(
            "scan.max_directory_visits must be a positive integer."
        )
    else:
        max_directory_visits = raw_limit

    section = ScanConfigSection(
        config_file_path=config_path,
        base_folders=base_folders,
        directory_names=directory_names,
        ignore_directories=ignore_directories,
        filename_patterns=filename_patterns,
        max_directory_visits=max_directory_visits,
    )

    return SearchConfiguration(
        config_file_path=section.config_file_path,
        execution_root=root_path,
        base_folders=section.base_folders,
        directory_names=section.directory_names,
        ignore_directories=section.ignore_directories,
        filename_patterns=section.filename_patterns,
        max_directory_visits=section.max_directory_visits,
    )


def _validate_patterns(scan_table: dict[str, Any], *, key: str) -> tuple[str, ...]:
    value = scan_table.get(key)

    if not isinstance(value, list) or not value:
        raise ConfigurationError(
            f"scan.{key} must be a non-empty array of pattern strings."
        )

    patterns: list[str] = []
    for index, raw_value in enumerate(value, start=1):
        if not isinstance(raw_value, str):
            raise ConfigurationError(f"scan.{key}[{index}] must be a string pattern.")

        normalized = raw_value.strip()
        if not normalized:
            raise ConfigurationError(
                f"scan.{key}[{index}] must not be blank or whitespace-only."
            )
        patterns.append(normalized)

    return tuple(patterns)


def _validate_optional_patterns(
    scan_table: dict[str, Any], *, key: str
) -> tuple[str, ...]:
    """Like _validate_patterns but allows empty (meaning 'none' for hints/ignores)."""
    value = scan_table.get(key)

    if value is None:
        return ()

    if not isinstance(value, list):
        raise ConfigurationError(
            f"scan.{key} must be an array of pattern strings (or omitted/empty)."
        )

    if not value:
        return ()

    patterns: list[str] = []
    for index, raw_value in enumerate(value, start=1):
        if not isinstance(raw_value, str):
            raise ConfigurationError(f"scan.{key}[{index}] must be a string pattern.")

        normalized = raw_value.strip()
        if not normalized:
            raise ConfigurationError(
                f"scan.{key}[{index}] must not be blank or whitespace-only."
            )
        patterns.append(normalized)

    return tuple(patterns)
