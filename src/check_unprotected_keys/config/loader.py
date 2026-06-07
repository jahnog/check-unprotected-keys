"""Configuration loading for the scanner."""

from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from check_unprotected_keys.config.models import ScanConfigSection
from check_unprotected_keys.domain.models import SearchConfiguration

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
            "Configuration file must define a [scan] table with folder_patterns "
            "and filename_patterns."
        )

    section = ScanConfigSection(
        config_file_path=config_path,
        folder_patterns=_validate_patterns(scan_table, key="folder_patterns"),
        filename_patterns=_validate_patterns(scan_table, key="filename_patterns"),
    )

    return SearchConfiguration(
        config_file_path=section.config_file_path,
        execution_root=root_path,
        folder_patterns=section.folder_patterns,
        filename_patterns=section.filename_patterns,
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
