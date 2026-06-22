"""Unit tests for start-folder scope narrowing.

Includes direct unit tests for resolve_start_folder covering the four states
(omitted, valid rel/abs, invalid cases) per the feature spec (US4), research,
and contracts/start-folder-validation.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unprotected_keys.adapters.filesystem import (
    discover_candidate_files,
    resolve_effective_scope,
)
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.scope import (
    build_effective_scope,
    narrow_root_directories,
    resolve_start_folder,
)
from tests.support.fixture_builders import (
    EXPANDED_FILENAME_PATTERNS,
    HOME_EXPANDED_FOLDER_PATTERN,
    create_expanded_pattern_workspace,
    write_expanded_scan_configuration,
)


def test_narrow_root_directories_replaces_parent_root_with_start_folder(
    tmp_path: Path,
) -> None:
    scope_root = tmp_path / "fixtures" / "default-scope"
    team_a_root = scope_root / "team-a"
    team_a_root.mkdir(parents=True)

    narrowed = narrow_root_directories((scope_root,), start_folder=team_a_root)

    assert narrowed == (team_a_root.resolve(),)


def test_narrow_root_directories_keeps_matching_nested_roots(tmp_path: Path) -> None:
    scope_root = tmp_path / "fixtures" / "default-scope"
    team_a_root = scope_root / "team-a"
    team_a_root.mkdir(parents=True)

    narrowed = narrow_root_directories((team_a_root,), start_folder=scope_root)

    assert narrowed == (team_a_root.resolve(),)


def test_narrow_root_directories_drops_unrelated_roots(tmp_path: Path) -> None:
    team_a_root = tmp_path / "team-a"
    team_b_root = tmp_path / "team-b"
    team_a_root.mkdir()
    team_b_root.mkdir()

    narrowed = narrow_root_directories((team_b_root,), start_folder=team_a_root)

    assert narrowed == ()


def test_build_effective_scope_preserves_filename_patterns_after_narrowing(
    tmp_path: Path,
) -> None:
    team_a_root = tmp_path / "fixtures" / "default-scope" / "team-a"
    team_a_root.mkdir(parents=True)

    scope = build_effective_scope((team_a_root,), ("id_*", "*_private.pem"))

    assert scope.filename_patterns == ("id_*", "*_private.pem")


def test_resolve_effective_scope_preserves_expanded_filename_patterns_after_narrowing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(workspace.root)
    configuration = load_search_configuration(workspace.root)

    scope = resolve_effective_scope(
        configuration,
        start_folder=workspace.repo_keys_root,
    )

    assert scope.root_directories == (workspace.repo_keys_root,)
    assert scope.filename_patterns == EXPANDED_FILENAME_PATTERNS


def test_resolve_effective_scope_respects_expanded_catalog_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(
        workspace.root,
        folder_patterns=(
            HOME_EXPANDED_FOLDER_PATTERN,
            "fixtures/expanded-patterns/repo-keys",
        ),
        filename_patterns=("id_*", "*.pem"),
    )
    configuration = load_search_configuration(workspace.root)

    scope = resolve_effective_scope(configuration, start_folder=None)

    assert scope.root_directories == (
        workspace.home_ssh_root,
        workspace.repo_keys_root,
    )
    assert scope.filename_patterns == ("id_*", "*.pem")


# New tests for resolve_start_folder (US4: omitted, passed/valid, invalid states).
# Exercise the unit per contracts/start-folder-validation.md + research decisions.
# Real FS chmod+restore for unreadable (no os.access monkeypatch).


def test_resolve_start_folder_omitted_returns_none(tmp_path: Path) -> None:
    """Omitted (None) returns None — full scope (US2 + US4)."""
    execution_root = tmp_path
    result = resolve_start_folder(execution_root, None)
    assert result is None


def test_resolve_start_folder_accepts_valid_relative(tmp_path: Path) -> None:
    """Valid relative path is resolved and returned (US1 + US4)."""
    sub = tmp_path / "sub" / "target"
    sub.mkdir(parents=True)
    result = resolve_start_folder(tmp_path, "sub/target")
    assert result == sub.resolve()
    assert result.is_absolute()
    assert result.is_dir()


def test_resolve_start_folder_accepts_valid_absolute(tmp_path: Path) -> None:
    """Valid absolute path is accepted (US1 + US4)."""
    sub = tmp_path / "abs-target"
    sub.mkdir()
    result = resolve_start_folder(tmp_path, str(sub))
    assert result == sub.resolve()
    assert result.is_absolute()


def test_resolve_start_folder_raises_for_nonexistent_path(tmp_path: Path) -> None:
    """Non-existent path raises with exact message (US3 + US4)."""
    with pytest.raises(ValueError, match="Start folder does not exist"):
        resolve_start_folder(tmp_path, "does/not/exist")


def test_resolve_start_folder_raises_for_file_instead_of_directory(
    tmp_path: Path,
) -> None:  # noqa: E501
    """File (not dir) raises exact message (US3 + US4)."""
    f = tmp_path / "somefile.txt"
    f.write_text("not a dir")
    with pytest.raises(ValueError, match="Start folder is not a directory"):
        resolve_start_folder(tmp_path, str(f))


def test_resolve_start_folder_raises_for_unreadable_directory(tmp_path: Path) -> None:
    """Unreadable dir raises exact msg; real chmod+restore (US3+US4, per research)."""
    sub = tmp_path / "unreadable-sub"
    sub.mkdir()
    try:
        sub.chmod(0o000)
        with pytest.raises(ValueError, match="Start folder is not readable"):
            resolve_start_folder(tmp_path, str(sub))
    finally:
        # Restore for tmp cleanup (project pattern in fixture_builders)
        sub.chmod(0o700)


# -------------------------------------------------------------------
# Dedicated unit tests for promotion + pruning + provenance (005 US2/US3)
# -------------------------------------------------------------------


def test_resolve_effective_scope_promotes_directory_hints(tmp_path: Path) -> None:
    """Promotion discovers hinted subdirs at depth under a base (T019)."""
    from tests.support.fixture_builders import write_scan_configuration

    base = tmp_path / "project"
    secrets = base / "apps" / "api" / "secrets"
    deploy = base / "services" / "bar" / "deploy"
    secrets.mkdir(parents=True)
    deploy.mkdir(parents=True)

    write_scan_configuration(
        tmp_path,
        base_folders=("project",),
        directory_names=("secrets", "deploy"),
        filename_patterns=("*.key", "id_*"),
    )
    configuration = load_search_configuration(tmp_path)

    scope = resolve_effective_scope(configuration, start_folder=None)

    roots = {p.relative_to(tmp_path) for p in scope.root_directories}
    assert Path("project") in roots
    assert Path("project/apps/api/secrets") in roots
    assert Path("project/services/bar/deploy") in roots

    # Provenance for promoted roots contains the hint
    assert "hint:secrets" in scope.root_provenance.get(secrets.resolve(), "")
    assert "hint:deploy" in scope.root_provenance.get(deploy.resolve(), "")


def test_resolve_effective_scope_pruning_prevents_promotion_and_walk(
    tmp_path: Path,
) -> None:
    """ignore_directories prevents both promotion and candidate discovery (T026)."""
    from tests.support.fixture_builders import write_scan_configuration

    base = tmp_path / "project"
    secrets = base / "apps" / "api" / "secrets"
    noise = base / "node_modules" / "pkg" / "secrets"  # same name as hint, but ignored
    secrets.mkdir(parents=True)
    noise.mkdir(parents=True)

    # A file that would match if not pruned
    (noise / "id_rsa").write_text("dummy", encoding="utf-8")
    (secrets / "id_rsa").write_text("dummy", encoding="utf-8")

    write_scan_configuration(
        tmp_path,
        base_folders=("project",),
        directory_names=("secrets",),
        # Replace semantics: only node_modules is pruned
        ignore_directories=("node_modules",),
        filename_patterns=("id_*",),
    )
    configuration = load_search_configuration(tmp_path)

    scope = resolve_effective_scope(configuration, start_folder=None)
    roots = {p.relative_to(tmp_path) for p in scope.root_directories}

    # The hinted "secrets" under apps is promoted; the one under node_modules is not
    assert Path("project/apps/api/secrets") in roots
    assert Path("project/node_modules/pkg/secrets") not in roots

    # When we actually discover candidates, the noise file must not appear
    # (pruning in discover_candidate_files + promotion)
    candidates, _ = discover_candidate_files(scope)
    cand_rel = {c.canonical_path.relative_to(tmp_path) for c in candidates}
    assert Path("project/apps/api/secrets/id_rsa") in cand_rel
    assert Path("project/node_modules/pkg/secrets/id_rsa") not in cand_rel


def test_promotion_and_base_coverage_produce_candidates_with_rich_labels(
    tmp_path: Path,
) -> None:
    """Candidates under promoted dirs get rich "base:..., hint:..." labels.

    Base-only files get a plain "base:..." label. (T020/T023)
    """
    from tests.support.fixture_builders import write_scan_configuration

    base = tmp_path / "ws"
    hinted = base / "config" / "secrets"
    non_hinted = base / "misc"
    hinted.mkdir(parents=True)
    non_hinted.mkdir(parents=True)

    (hinted / "deploy.key").write_text("pem-stuff", encoding="utf-8")
    (non_hinted / "id_rsa").write_text("pem-stuff", encoding="utf-8")

    write_scan_configuration(
        tmp_path,
        base_folders=("ws",),
        directory_names=("secrets",),
        filename_patterns=("*.key", "id_*"),
    )
    configuration = load_search_configuration(tmp_path)

    scope = resolve_effective_scope(configuration, start_folder=None)
    cands, _ = discover_candidate_files(scope)

    labels = {c.matched_folder_pattern for c in cands}
    # At least one rich promoted label
    assert any("hint:secrets" in lab and "base:" in lab for lab in labels)
    # At least one base-only label (the non-hinted id_rsa)
    assert any(lab.startswith("base:") and "hint:" not in lab for lab in labels)
