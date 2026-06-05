"""Unit tests for start-folder scope narrowing."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.adapters.filesystem import resolve_effective_scope
from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.scope import (
    build_effective_scope,
    narrow_root_directories,
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
