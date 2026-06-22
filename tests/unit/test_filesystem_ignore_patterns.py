"""Unit tests for filename ignore filtering during discovery."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.filesystem import discover_candidate_files
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
