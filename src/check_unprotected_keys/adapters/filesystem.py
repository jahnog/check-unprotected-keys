"""Filesystem discovery and candidate enumeration helpers."""

from __future__ import annotations

import fnmatch
import glob
import os
from dataclasses import dataclass
from pathlib import Path

from check_unprotected_keys.domain import scope as scope_domain
from check_unprotected_keys.domain.models import (
    CandidateFile,
    EffectiveScope,
    SearchConfiguration,
)


@dataclass(frozen=True, slots=True)
class DiscoveryIssue:
    """A non-fatal filesystem issue discovered while expanding scope."""

    location: Path
    error_type: str


def resolve_effective_scope(
    configuration: SearchConfiguration,
    *,
    start_folder: Path | None,
) -> EffectiveScope:
    """Resolve folder patterns and apply optional start-folder narrowing."""

    matched_roots = []
    for pattern in configuration.folder_patterns:
        matched_roots.extend(
            _expand_folder_pattern(configuration.execution_root, pattern)
        )

    narrowed_roots = scope_domain.narrow_root_directories(
        matched_roots,
        start_folder=start_folder,
    )
    return scope_domain.build_effective_scope(
        narrowed_roots,
        configuration.filename_patterns,
    )


def discover_candidate_files(
    scope: EffectiveScope,
) -> tuple[list[CandidateFile], list[DiscoveryIssue]]:
    """Enumerate unique candidate files inside the effective scope."""

    candidates: list[CandidateFile] = []
    issues: list[DiscoveryIssue] = []
    seen_paths: set[Path] = set()

    for root_directory in scope.root_directories:
        root_label = str(root_directory)

        def on_error(
            error: OSError,
            *,
            current_root: Path = root_directory,
        ) -> None:
            location = Path(error.filename) if error.filename else current_root
            issues.append(
                DiscoveryIssue(location=location, error_type=type(error).__name__)
            )

        for current_root, _, file_names in os.walk(
            root_directory,
            topdown=True,
            onerror=on_error,
            followlinks=False,
        ):
            current_path = Path(current_root)
            for file_name in file_names:
                matched_filename_pattern = _match_filename_pattern(
                    file_name,
                    scope.filename_patterns,
                )
                if matched_filename_pattern is None:
                    continue

                candidate_path = current_path / file_name
                try:
                    canonical_path = candidate_path.resolve(strict=True)
                except OSError as exc:
                    issues.append(
                        DiscoveryIssue(
                            location=candidate_path,
                            error_type=type(exc).__name__,
                        )
                    )
                    continue

                if canonical_path in seen_paths:
                    continue
                seen_paths.add(canonical_path)

                candidates.append(
                    CandidateFile(
                        canonical_path=canonical_path,
                        display_path=str(canonical_path),
                        matched_folder_pattern=root_label,
                        matched_filename_pattern=matched_filename_pattern,
                    )
                )

    return candidates, issues


def _expand_folder_pattern(execution_root: Path, pattern: str) -> list[Path]:
    base_path = Path(pattern).expanduser()
    pattern_text = str(
        base_path if base_path.is_absolute() else execution_root / base_path
    )

    if glob.has_magic(pattern_text):
        matches = glob.glob(pattern_text, recursive=True)
    else:
        matches = [pattern_text]

    directories: list[Path] = []
    for match in matches:
        candidate = Path(match)
        if candidate.is_dir():
            directories.append(candidate.resolve())
    return directories


def _match_filename_pattern(file_name: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatch(file_name, pattern):
            return pattern
    return None
