"""Typed configuration structures for scan settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScanConfigSection:
    """Raw scan settings loaded from the TOML configuration document."""

    config_file_path: Path
    folder_patterns: tuple[str, ...]
    filename_patterns: tuple[str, ...]
