"""Scope resolution helpers for effective scan directories."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from check_unprotected_keys.domain.models import EffectiveScope


def resolve_start_folder(execution_root: Path, raw_value: str | None) -> Path | None:
    """Resolve and validate the optional start folder argument."""

    if raw_value is None:
        return None

    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = execution_root / candidate

    resolved = candidate.resolve()
    if not resolved.exists():
        raise ValueError(f"Start folder does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Start folder is not a directory: {resolved}")
    if not os.access(resolved, os.R_OK):
        raise ValueError(f"Start folder is not readable: {resolved}")
    return resolved


def narrow_root_directories(
    root_directories: Iterable[Path],
    *,
    start_folder: Path | None,
) -> tuple[Path, ...]:
    """Restrict matched root directories to those beneath the optional start folder."""

    canonical_roots = tuple(path.resolve() for path in root_directories)
    if start_folder is None:
        return canonical_roots

    filtered: list[Path] = []
    seen_paths: set[Path] = set()
    for path in canonical_roots:
        narrowed_path: Path | None = None
        if path == start_folder or path.is_relative_to(start_folder):
            narrowed_path = path
        elif start_folder.is_relative_to(path):
            narrowed_path = start_folder

        if narrowed_path is None or narrowed_path in seen_paths:
            continue

        filtered.append(narrowed_path)
        seen_paths.add(narrowed_path)

    return tuple(filtered)


def build_effective_scope(
    root_directories: Iterable[Path],
    filename_patterns: Iterable[str],
    *,
    ignore_directories: Iterable[str] | None = None,
    ignore_filename_patterns: Iterable[str] | None = None,
    root_provenance: dict[Path, str] | None = None,
) -> EffectiveScope:
    """Create an immutable effective scope from resolved directories and patterns."""

    canonical_roots: list[Path] = []
    seen_paths: set[Path] = set()
    for path in root_directories:
        canonical_path = path.resolve()
        if canonical_path in seen_paths:
            continue
        canonical_roots.append(canonical_path)
        seen_paths.add(canonical_path)

    ignores = frozenset(ignore_directories or ())
    filename_ignores = frozenset(ignore_filename_patterns or ())
    provenance = dict(root_provenance or {})

    return EffectiveScope(
        root_directories=tuple(canonical_roots),
        filename_patterns=tuple(filename_patterns),
        canonical_root_set=frozenset(canonical_roots),
        ignore_directories=ignores,
        ignore_filename_patterns=filename_ignores,
        root_provenance=provenance,
    )
