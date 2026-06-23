"""Configuration loading for the scanner."""

from __future__ import annotations

import functools
import glob
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from check_unprotected_keys.config.models import ScanConfigSection
from check_unprotected_keys.domain.models import SearchConfiguration

DEFAULT_CONFIG_FILENAME = ".check-unprotected-keys.toml"

_PARTIAL_LEGACY_SENTINELS = frozenset({".git", "node_modules"})


class ConfigurationError(ValueError):
    """Raised when runtime scan configuration is missing or invalid."""


def read_example_configuration_text() -> str:
    """Return the packaged example configuration for installed users."""

    resource = files("check_unprotected_keys.resources").joinpath(
        "check-unprotected-keys.example.toml"
    )
    return resource.read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def _load_packaged_defaults() -> tuple[
    tuple[str, ...], tuple[str, ...], tuple[str, ...]
]:
    """Return packaged ignore_directories, ignore_filename_patterns,
    and property_name_patterns defaults."""

    resource = files("check_unprotected_keys.resources").joinpath(
        "check-unprotected-keys.example.toml"
    )
    document = tomllib.loads(resource.read_text(encoding="utf-8"))
    scan_table = document.get("scan")
    if not isinstance(scan_table, dict):
        raise ConfigurationError(
            "Packaged example configuration is missing a [scan] table."
        )

    dir_defaults = _validate_optional_patterns(scan_table, key="ignore_directories")
    file_defaults = _validate_optional_patterns(
        scan_table, key="ignore_filename_patterns"
    )
    property_defaults = _validate_optional_patterns(
        scan_table, key="property_name_patterns"
    )
    if not dir_defaults or not file_defaults or not property_defaults:
        raise ConfigurationError(
            "Packaged example configuration must define non-empty "
            "ignore_directories, ignore_filename_patterns, and "
            "property_name_patterns defaults."
        )
    return dir_defaults, file_defaults, property_defaults


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

    (
        packaged_dir_ignores,
        packaged_file_ignores,
        packaged_property_names,
    ) = _load_packaged_defaults()

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
        directory_names = tuple(
            p for p in base_folders if "/" not in p and not glob.has_magic(p)
        )
    else:
        directory_names = ()

    ignore_directories, ignore_dirs_present = _resolve_ignore_list(
        scan_table,
        key="ignore_directories",
        packaged_defaults=packaged_dir_ignores,
    )
    ignore_filename_patterns, _ = _resolve_ignore_list(
        scan_table,
        key="ignore_filename_patterns",
        packaged_defaults=packaged_file_ignores,
    )
    property_name_patterns, _ = _resolve_ignore_list(
        scan_table,
        key="property_name_patterns",
        packaged_defaults=packaged_property_names,
    )

    load_warnings: list[str] = []
    partial_warning = _maybe_partial_legacy_ignore_warning(
        key_was_present=ignore_dirs_present,
        resolved=ignore_directories,
        packaged=packaged_dir_ignores,
    )
    if partial_warning is not None:
        load_warnings.append(partial_warning)

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
        ignore_filename_patterns=ignore_filename_patterns,
        filename_patterns=filename_patterns,
        property_name_patterns=property_name_patterns,
        max_directory_visits=max_directory_visits,
        load_warnings=tuple(load_warnings),
    )

    return SearchConfiguration(
        config_file_path=section.config_file_path,
        execution_root=root_path,
        base_folders=section.base_folders,
        directory_names=section.directory_names,
        ignore_directories=section.ignore_directories,
        ignore_filename_patterns=section.ignore_filename_patterns,
        filename_patterns=section.filename_patterns,
        property_name_patterns=section.property_name_patterns,
        max_directory_visits=section.max_directory_visits,
        load_warnings=section.load_warnings,
    )


def _resolve_ignore_list(
    scan_table: dict[str, Any],
    *,
    key: str,
    packaged_defaults: tuple[str, ...],
) -> tuple[tuple[str, ...], bool]:
    """Resolve omit / empty / replace semantics for an ignore list key.

    Returns (effective_list, key_was_present_in_user_toml).
    """

    if key not in scan_table:
        return packaged_defaults, False

    user_patterns = _validate_optional_patterns(scan_table, key=key)
    if not user_patterns:
        return (), True
    return tuple(dict.fromkeys(user_patterns)), True


def _maybe_partial_legacy_ignore_warning(
    *,
    key_was_present: bool,
    resolved: tuple[str, ...],
    packaged: tuple[str, ...],
) -> str | None:
    """Detect likely legacy partial extension lists under replace semantics."""

    if not key_was_present or not resolved:
        return None
    if len(resolved) >= len(packaged) / 2:
        return None
    if _PARTIAL_LEGACY_SENTINELS.issubset(set(resolved)):
        return None
    return (
        "warning: scan.ignore_directories looks like a partial extension list from "
        "an older release. Under replace semantics only the configured names are "
        "pruned. Copy the packaged defaults from --print-example-config and merge "
        "your custom entries."
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
