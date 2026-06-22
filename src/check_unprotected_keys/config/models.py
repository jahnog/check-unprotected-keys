"""Typed configuration structures for scan settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScanConfigSection:
    """Raw scan settings loaded from the TOML configuration document.

    base_folders (or legacy folder_patterns) are the search bases.
    directory_names and ignore_directories support the broad discovery model.
    """

    config_file_path: Path
    base_folders: tuple[str, ...]
    directory_names: tuple[str, ...]
    ignore_directories: tuple[str, ...]
    ignore_filename_patterns: tuple[str, ...]
    filename_patterns: tuple[str, ...]
    max_directory_visits: int = 100_000
    load_warnings: tuple[str, ...] = ()
