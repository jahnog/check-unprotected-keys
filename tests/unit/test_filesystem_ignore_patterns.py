"""Unit tests for filename ignore filtering during discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unprotected_keys.adapters.filesystem import (
    DiscoveryIssue,
    discover_candidate_files,
    resolve_effective_scope,
)
from check_unprotected_keys.domain.models import SearchConfiguration
from check_unprotected_keys.domain.scope import build_effective_scope


def test_ignore_filename_pattern_skips_overlap_before_inclusion(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    (keys_dir / "id_rsa").write_text("private", encoding="utf-8")
    (keys_dir / "id_rsa.pub").write_text("public", encoding="utf-8")

    scope = build_effective_scope(
        (keys_dir,),
        ("id_*",),
        ignore_filename_patterns=("*.pub",),
    )

    candidates, _ = discover_candidate_files(scope)
    names = {c.canonical_path.name for c in candidates}

    assert names == {"id_rsa"}


def test_path_ignore_prunes_only_that_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path ignore skips one directory, including under a promoted parent.

    Another directory with the same basename stays visible. A ``~`` entry
    expands against HOME.
    """

    home = tmp_path / "home"
    ignored = home / ".local" / "share" / "docker" / "containerd" / "daemon"
    ignored_secret = ignored / "secrets"
    ignored_secret.mkdir(parents=True)
    (ignored / "id_ed25519").write_text("hidden", encoding="utf-8")
    (ignored_secret / "id_rsa").write_text("hidden", encoding="utf-8")

    other = home / "work" / "daemon"
    other.mkdir(parents=True)
    (other / "id_rsa").write_text("keep", encoding="utf-8")

    kept_hint = home / "work" / "secrets"
    kept_hint.mkdir()
    (kept_hint / "id_rsa").write_text("keep", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    configuration = SearchConfiguration(
        config_file_path=tmp_path / ".check-unprotected-keys.toml",
        execution_root=tmp_path,
        base_folders=(str(home),),
        directory_names=("secrets", "docker"),
        ignore_directories=("~/.local/share/docker/containerd/daemon",),
        ignore_filename_patterns=(),
        filename_patterns=("id_*",),
    )

    scope = resolve_effective_scope(configuration, start_folder=None)
    roots = set(scope.root_directories)
    assert kept_hint.resolve() in roots
    assert ignored_secret.resolve() not in roots

    candidates, _issues = discover_candidate_files(scope)
    found = {candidate.canonical_path for candidate in candidates}
    assert (other / "id_rsa").resolve() in found
    assert (kept_hint / "id_rsa").resolve() in found
    assert (ignored / "id_ed25519").resolve() not in found
    assert (ignored_secret / "id_rsa").resolve() not in found


def test_relative_path_ignore_skips_that_root_and_its_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative path ignore is cwd-based, including when it is the walk root."""

    root = tmp_path / "project"
    ignored = root / "containerd" / "daemon"
    ignored.mkdir(parents=True)
    (ignored / "id_rsa").write_text("hidden", encoding="utf-8")
    (root / "id_rsa").write_text("keep", encoding="utf-8")
    monkeypatch.chdir(root)

    configuration = SearchConfiguration(
        config_file_path=root / ".check-unprotected-keys.toml",
        execution_root=root,
        base_folders=(".", "containerd/daemon"),
        directory_names=(),
        ignore_directories=("containerd/daemon",),
        ignore_filename_patterns=(),
        filename_patterns=("id_*",),
    )

    scope = resolve_effective_scope(configuration, start_folder=None)
    candidates, _issues = discover_candidate_files(scope)
    found = {candidate.canonical_path for candidate in candidates}

    assert (root / "id_rsa").resolve() in found
    assert (ignored / "id_rsa").resolve() not in found


def test_empty_ignore_filename_patterns_allows_overlap_candidates(
    tmp_path: Path,
) -> None:
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    (keys_dir / "id_rsa.pub").write_text("public", encoding="utf-8")

    scope = build_effective_scope(
        (keys_dir,),
        ("id_*",),
        ignore_filename_patterns=(),
    )

    candidates, _ = discover_candidate_files(scope)
    names = {c.canonical_path.name for c in candidates}

    assert names == {"id_rsa.pub"}


def test_promotion_pass_records_unreadable_directories_as_issues(
    tmp_path: Path,
) -> None:
    """The directory-name promotion walk must not swallow OSError silently
    (spec 010 A2/FR-001): unreadable directories surface as DiscoveryIssues.
    """

    base = tmp_path / "project"
    hidden = base / "hidden"
    hidden.mkdir(parents=True)
    (base / "secrets").mkdir()
    hidden.chmod(0)

    configuration = SearchConfiguration(
        config_file_path=tmp_path / ".check-unprotected-keys.toml",
        execution_root=tmp_path,
        base_folders=(str(base),),
        directory_names=("secrets",),
        ignore_directories=(),
        ignore_filename_patterns=(),
        filename_patterns=("id_*",),
    )

    issues: list[DiscoveryIssue] = []
    try:
        resolve_effective_scope(configuration, start_folder=None, issues=issues)
    finally:
        hidden.chmod(0o755)

    assert any(issue.location == hidden for issue in issues)
    assert all(issue.error_type for issue in issues)
    assert all(
        issue.phase.value == "directory-promotion"
        for issue in issues
        if issue.location == hidden
    )


def test_concrete_file_base_records_scope_resolution_issue(tmp_path: Path) -> None:
    """A non-glob base that exists but is not a directory is not silent."""

    not_a_dir = tmp_path / "looks-like-base"
    not_a_dir.write_text("not a directory", encoding="utf-8")

    configuration = SearchConfiguration(
        config_file_path=tmp_path / ".check-unprotected-keys.toml",
        execution_root=tmp_path,
        base_folders=(str(not_a_dir),),
        directory_names=(),
        ignore_directories=(),
        ignore_filename_patterns=(),
        filename_patterns=("id_*",),
    )

    issues: list[DiscoveryIssue] = []
    scope = resolve_effective_scope(configuration, start_folder=None, issues=issues)

    assert scope.root_directories == ()
    assert len(issues) == 1
    assert issues[0].location == not_a_dir.resolve()
    assert issues[0].error_type == "NotADirectory"
    assert issues[0].phase.value == "scope-resolution"


def test_shared_budget_limits_promotion_plus_discovery(tmp_path: Path) -> None:
    """Promotion and discovery share one visit budget (not independent 2× caps)."""

    from check_unprotected_keys.adapters.filesystem import (
        DirectoryLimitExceededError,
        VisitedDirectoryTracker,
        discover_candidate_files,
    )

    base = tmp_path / "project"
    # Deep enough that promotion alone does not exhaust a tiny budget of 2 when
    # discovery also needs to enter roots.
    (base / "a" / "b" / "secrets").mkdir(parents=True)
    (base / "a" / "b" / "secrets" / "id_rsa").write_text("k", encoding="utf-8")

    configuration = SearchConfiguration(
        config_file_path=tmp_path / ".check-unprotected-keys.toml",
        execution_root=tmp_path,
        base_folders=(str(base),),
        directory_names=("secrets",),
        ignore_directories=(),
        ignore_filename_patterns=(),
        filename_patterns=("id_*",),
        max_directory_visits=3,
    )

    tracker = VisitedDirectoryTracker(limit=3)
    issues: list[DiscoveryIssue] = []
    try:
        scope = resolve_effective_scope(
            configuration,
            start_folder=None,
            visited_tracker=tracker,
            issues=issues,
        )
        discover_candidate_files(scope, visited_tracker=tracker)
        # If neither phase raised, the shared budget must still be respected.
        assert tracker.budget.used <= 3
    except DirectoryLimitExceededError as error:
        assert error.limit == 3
        assert tracker.budget.used == 3
