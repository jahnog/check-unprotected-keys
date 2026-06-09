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
    """Resolve search bases (and later directory name promotion + pruning)
    and apply optional start-folder narrowing.
    """

    matched_roots = []
    for pattern in configuration.base_folders:
        matched_roots.extend(
            _expand_folder_pattern(configuration.execution_root, pattern)
        )

    narrowed_roots = scope_domain.narrow_root_directories(
        matched_roots,
        start_folder=start_folder,
    )

    # Directory name promotion (US2): discover additional high-value subdirs
    # under the (already narrowed) bases.
    ignore_set = frozenset(configuration.ignore_directories)
    promoted, sub_provenance = _discover_promoted_directories(
        narrowed_roots,
        configuration.directory_names,
        ignore_set,
        start_folder=start_folder,
    )

    # Put promoted (more specific) roots first so that files under them
    # are claimed with the rich "base:..., hint:..." label during the first
    # walk that reaches them (before any ancestor base walk).
    all_roots = promoted + list(narrowed_roots)

    # Build full provenance map for rich matched_folder_pattern labels
    # (bases get "base:...", promoted get "base:..., hint:..." from the sub map).
    provenance: dict[Path, str] = {}
    for b in narrowed_roots:
        provenance[b] = f"base:{b}"
    provenance.update(sub_provenance)

    return scope_domain.build_effective_scope(
        all_roots,
        configuration.filename_patterns,
        ignore_directories=configuration.ignore_directories,
        root_provenance=provenance,
    )


def discover_candidate_files(
    scope: EffectiveScope,
) -> tuple[list[CandidateFile], list[DiscoveryIssue]]:
    """Enumerate unique candidate files inside the effective scope."""

    candidates: list[CandidateFile] = []
    issues: list[DiscoveryIssue] = []
    seen_paths: set[Path] = set()

    for root_directory in scope.root_directories:
        # Use rich provenance label ("base:..., hint:...") when available (for
        # candidates under promoted directories); fall back to the raw path.
        root_label = scope.root_provenance.get(root_directory, str(root_directory))

        def on_error(
            error: OSError,
            *,
            current_root: Path = root_directory,
        ) -> None:
            location = Path(error.filename) if error.filename else current_root
            issues.append(
                DiscoveryIssue(location=location, error_type=type(error).__name__)
            )

        ignore_set = scope.ignore_directories or frozenset()
        for current_root, dirnames, file_names in os.walk(
            root_directory,
            topdown=True,
            onerror=on_error,
            followlinks=False,
        ):
            # Apply pruning for broad bases (US3)
            if ignore_set:
                dirnames[:] = [d for d in dirnames if d not in ignore_set]

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


def _discover_promoted_directories(
    bases: list[Path] | tuple[Path, ...],
    directory_names: tuple[str, ...],
    ignore_names: frozenset[str],
    *,
    start_folder: Path | None = None,
) -> tuple[list[Path], dict[Path, str]]:
    """Discover subdirectories under bases whose basename is in directory_names.

    Respects ignore_names (never descend). Respects start_folder for narrowing.
    Returns (resolved unique promoted directories, sub-provenance map for them).
    Provenance values are of the form "base:{base}, hint:{hint}".
    Bases themselves are *not* included here (caller labels them).
    """
    if not directory_names:
        return [], {}

    hint_set = set(directory_names)
    promoted: list[Path] = []
    seen: set[Path] = set()
    sub_provenance: dict[Path, str] = {}

    for base in bases:
        if not base.is_dir():
            continue
        base_str = str(base)

        # Use topdown walk so we can prune ignores on the fly
        for dirpath, dirnames, _ in os.walk(base, topdown=True, followlinks=False):
            current = Path(dirpath)

            # Prune ignores in-place for efficiency
            dirnames[:] = [d for d in dirnames if d not in ignore_names]

            # Check if this dir itself is a hinted one (but not the base root itself
            # unless it matches, which is already included via bases)
            if current != base and current.name in hint_set:
                try:
                    canon = current.resolve(strict=True)
                except OSError:
                    continue
                if canon not in seen and (
                    start_folder is None
                    or canon == start_folder
                    or canon.is_relative_to(start_folder)
                    or start_folder.is_relative_to(canon)
                ):
                    promoted.append(canon)
                    seen.add(canon)
                    sub_provenance[canon] = f"base:{base_str}, hint:{current.name}"

            # If we are deeper than needed or under ignored, the walk
            # will handle pruning via the dirnames mutation above.

    return promoted, sub_provenance
