"""Filesystem discovery and candidate enumeration helpers."""

from __future__ import annotations

import fnmatch
import glob
import logging
import os
from pathlib import Path

from check_unprotected_keys.domain import models as domain_models
from check_unprotected_keys.domain import scope as scope_domain
from check_unprotected_keys.domain.discovery import (
    DirectoryLimitExceededError,
    DirectoryVisitBudget,
    DiscoveryIssue,
    VisitedDirectoryTracker,
)
from check_unprotected_keys.domain.models import (
    CandidateFile,
    EffectiveScope,
    SearchConfiguration,
    SkipPhase,
)

# Re-export discovery types so existing adapter imports keep working.
__all__ = [
    "DirectoryLimitExceededError",
    "DirectoryVisitBudget",
    "DiscoveryIssue",
    "VisitedDirectoryTracker",
    "discover_candidate_files",
    "resolve_effective_scope",
]

_logger = logging.getLogger(__name__)


def _is_path_ignore_entry(entry: str) -> bool:
    """True when an ignore entry names one directory instead of a basename."""

    return "/" in entry or entry.startswith("~")


def _compile_directory_ignores(
    ignore_set: frozenset[str],
) -> tuple[frozenset[str], frozenset[Path]]:
    """Split basename ignores from path ignores.

    Path entries (contain ``/`` or start with ``~``) are tilde-expanded and
    resolved once per walk. Basename entries stay exact name matches.
    """

    names: set[str] = set()
    paths: set[Path] = set()
    for entry in ignore_set:
        if _is_path_ignore_entry(entry):
            path = Path(entry).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            # Keep both forms: os.walk reports the path it was given, while
            # resolve() follows symlinks along that path.
            paths.add(path.absolute())
            paths.add(path.resolve(strict=False))
        else:
            names.add(entry)
    return frozenset(names), frozenset(paths)


def _path_matches_ignore(path: Path, ignore_paths: frozenset[Path]) -> bool:
    return any(path.is_relative_to(ignored) for ignored in ignore_paths)


def _prune_with_visit_check(
    dirnames: list[str],
    current_path: Path,
    ignore_names: frozenset[str],
    ignore_paths: frozenset[Path],
    tracker: VisitedDirectoryTracker,
    issues: list[DiscoveryIssue] | None = None,
    *,
    phase: SkipPhase = SkipPhase.CANDIDATE_DISCOVERY,
) -> bool:
    """Mutate dirnames in-place: remove ignored, already-visited, or inaccessible dirs.

    Returns True when ``current_path`` itself lies in an ignored path, so the
    caller must not read or promote it. Raises DirectoryLimitExceededError if
    the tracker cap is hit.
    """
    if ignore_paths and _path_matches_ignore(current_path, ignore_paths):
        dirnames[:] = []
        return True

    safe: list[str] = []
    for name in dirnames:
        if name in ignore_names:
            continue
        sub = current_path / name
        if ignore_paths and _path_matches_ignore(sub, ignore_paths):
            continue
        try:
            if tracker.try_visit(sub):
                safe.append(name)
            else:
                _logger.debug("skipping already-visited directory: %s", sub)
        except DirectoryLimitExceededError:
            raise
        except OSError as exc:
            _logger.debug("skipping inaccessible link: %s (%s)", sub, exc)
            if issues is not None:
                issues.append(
                    DiscoveryIssue(
                        location=sub,
                        error_type=type(exc).__name__,
                        phase=phase,
                    )
                )
    dirnames[:] = safe
    return False


def resolve_effective_scope(
    configuration: SearchConfiguration,
    *,
    start_folder: Path | None,
    visited_tracker: VisitedDirectoryTracker | None = None,
    issues: list[DiscoveryIssue] | None = None,
) -> EffectiveScope:
    """Resolve search bases (and later directory name promotion + pruning)
    and apply optional start-folder narrowing.

    Non-fatal filesystem errors met during base expansion and the promotion
    walk are appended to ``issues`` when a list is provided (FR-001).

    Promotion uses a fresh cycle-detection set but shares the caller's visit
    budget so ``max_directory_visits`` is a single hard cap across phases.
    """

    matched_roots: list[Path] = []
    for pattern in configuration.base_folders:
        matched_roots.extend(
            _expand_folder_pattern(
                configuration.execution_root,
                pattern,
                issues=issues,
            )
        )

    narrowed_roots = scope_domain.narrow_root_directories(
        matched_roots,
        start_folder=start_folder,
    )

    # Directory name promotion (US2): discover additional high-value subdirs
    # under the (already narrowed) bases.
    ignore_set = frozenset(configuration.ignore_directories)
    # Fresh cycle set so discovery can still enter bases; shared budget so the
    # configured visit cap is not doubled across promotion + discovery.
    budget = (
        visited_tracker.budget
        if visited_tracker is not None
        else DirectoryVisitBudget(configuration.max_directory_visits)
    )
    promote_tracker = VisitedDirectoryTracker(budget=budget)
    promoted, sub_provenance = _discover_promoted_directories(
        narrowed_roots,
        configuration.directory_names,
        ignore_set,
        start_folder=start_folder,
        visited_tracker=promote_tracker,
        issues=issues,
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
        ignore_filename_patterns=configuration.ignore_filename_patterns,
        root_provenance=provenance,
    )


def discover_candidate_files(
    scope: EffectiveScope,
    *,
    visited_tracker: VisitedDirectoryTracker | None = None,
) -> tuple[list[CandidateFile], list[DiscoveryIssue]]:
    """Enumerate unique candidate files inside the effective scope."""

    tracker = visited_tracker or VisitedDirectoryTracker(
        limit=domain_models.DEFAULT_MAX_DIRECTORY_VISITS
    )
    candidates: list[CandidateFile] = []
    issues: list[DiscoveryIssue] = []
    seen_paths: set[Path] = set()

    try:
        _walk_candidate_roots(scope, tracker, candidates, issues, seen_paths)
    except DirectoryLimitExceededError as error:
        # Preserve what was gathered before the cap so callers can report
        # partial results (FR-002) instead of discarding everything.
        error.partial_candidates = tuple(candidates)
        error.partial_issues = tuple(issues)
        raise

    return candidates, issues


def _walk_candidate_roots(
    scope: EffectiveScope,
    tracker: VisitedDirectoryTracker,
    candidates: list[CandidateFile],
    issues: list[DiscoveryIssue],
    seen_paths: set[Path],
) -> None:
    discovery_phase = SkipPhase.CANDIDATE_DISCOVERY
    ignore_names, ignore_paths = _compile_directory_ignores(
        scope.ignore_directories or frozenset()
    )
    for root_directory in scope.root_directories:
        # Mark root as visited; skip if already entered in this discovery pass.
        try:
            if not tracker.try_visit(root_directory):
                _logger.debug("skipping already-visited root: %s", root_directory)
                continue
        except OSError as exc:
            issues.append(
                DiscoveryIssue(
                    location=root_directory,
                    error_type=type(exc).__name__,
                    phase=discovery_phase,
                )
            )
            continue

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
                DiscoveryIssue(
                    location=location,
                    error_type=type(error).__name__,
                    phase=discovery_phase,
                )
            )

        for current_root, dirnames, file_names in os.walk(
            root_directory,
            topdown=True,
            onerror=on_error,
            followlinks=True,
        ):
            current_path = Path(current_root)
            if _prune_with_visit_check(
                dirnames,
                current_path,
                ignore_names,
                ignore_paths,
                tracker,
                issues,
                phase=discovery_phase,
            ):
                continue

            for file_name in file_names:
                if scope.ignore_filename_patterns and _match_filename_pattern(
                    file_name,
                    tuple(scope.ignore_filename_patterns),
                ):
                    continue

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
                            phase=discovery_phase,
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


def _expand_folder_pattern(
    execution_root: Path,
    pattern: str,
    *,
    issues: list[DiscoveryIssue] | None = None,
) -> list[Path]:
    """Expand one base_folders pattern into concrete directories.

    Non-glob paths that exist but are not usable directories are recorded as
    ``SCOPE_RESOLUTION`` issues when ``issues`` is provided (FR-001). Globs that
    match nothing are not treated as discovered skips.
    """

    base_path = Path(pattern).expanduser()
    pattern_text = str(
        base_path if base_path.is_absolute() else execution_root / base_path
    )
    is_glob = glob.has_magic(pattern_text)

    if is_glob:
        matches = glob.glob(pattern_text, recursive=True)
    else:
        matches = [pattern_text]

    directories: list[Path] = []
    for match in matches:
        candidate = Path(match)
        try:
            if candidate.is_dir():
                directories.append(candidate.resolve())
            elif not is_glob and candidate.exists():
                # Concrete path present but not a directory (e.g. a file).
                if issues is not None:
                    issues.append(
                        DiscoveryIssue(
                            location=candidate.resolve(strict=False),
                            error_type="NotADirectory",
                            phase=SkipPhase.SCOPE_RESOLUTION,
                        )
                    )
        except OSError as exc:
            if not is_glob and issues is not None:
                issues.append(
                    DiscoveryIssue(
                        location=candidate,
                        error_type=type(exc).__name__,
                        phase=SkipPhase.SCOPE_RESOLUTION,
                    )
                )
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
    visited_tracker: VisitedDirectoryTracker,
    issues: list[DiscoveryIssue] | None = None,
) -> tuple[list[Path], dict[Path, str]]:
    """Discover subdirectories under bases whose basename is in directory_names.

    Respects ignore_names (never descend). Respects start_folder for narrowing.
    Returns (resolved unique promoted directories, sub-provenance map for them).
    Provenance values are of the form "base:{base}, hint:{hint}".
    Bases themselves are *not* included here (caller labels them).
    Non-fatal filesystem errors are appended to ``issues`` when provided.
    """
    if not directory_names:
        return [], {}

    promotion_phase = SkipPhase.DIRECTORY_PROMOTION

    def _record_issue(location: Path, error: OSError) -> None:
        if issues is not None:
            issues.append(
                DiscoveryIssue(
                    location=location,
                    error_type=type(error).__name__,
                    phase=promotion_phase,
                )
            )

    hint_set = set(directory_names)
    basename_ignores, path_ignores = _compile_directory_ignores(ignore_names)
    promoted: list[Path] = []
    seen: set[Path] = set()
    sub_provenance: dict[Path, str] = {}

    for base in bases:
        if not base.is_dir():
            continue

        # Mark base as visited; skip if already entered.
        try:
            if not visited_tracker.try_visit(base):
                _logger.debug("skipping already-visited base in hint pass: %s", base)
                continue
        except OSError as exc:
            _record_issue(base, exc)
            continue

        base_str = str(base)

        def _on_walk_error(error: OSError, *, current_base: Path = base) -> None:
            location = Path(error.filename) if error.filename else current_base
            _record_issue(location, error)

        # Use topdown walk with symlink following so we can prune ignores and cycles.
        for dirpath, dirnames, _ in os.walk(
            base, topdown=True, onerror=_on_walk_error, followlinks=True
        ):
            current = Path(dirpath)
            if _prune_with_visit_check(
                dirnames,
                current,
                basename_ignores,
                path_ignores,
                visited_tracker,
                issues,
                phase=promotion_phase,
            ):
                continue

            # Check if this dir itself is a hinted one (but not the base root itself
            # unless it matches, which is already included via bases)
            if current != base and current.name in hint_set:
                try:
                    canon = current.resolve(strict=True)
                except OSError as exc:
                    _record_issue(current, exc)
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

    return promoted, sub_provenance
