"""Unit tests for the ``.properties`` inspector adapter."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.properties_inspector import (
    PropertyFindingOrigin,
    inspect_properties_file,
)
from check_unprotected_keys.domain.models import EffectiveScope

from ..support.fixture_builders import write_pem_private_key

_PATTERNS = ("password", "secret", "private", "key", "token")


def _scope(root: Path) -> EffectiveScope:
    resolved = root.resolve()
    return EffectiveScope(
        root_directories=(resolved,),
        filename_patterns=("*.properties",),
        canonical_root_set=frozenset({resolved}),
    )


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_plaintext_secret_is_reported(tmp_path: Path) -> None:
    props = _write(
        tmp_path / "app.properties", "db.password=hunter2xyz\nserver.port=8080\n"
    )

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [(f.property_key, f.origin) for f in result.findings] == [
        ("db.password", PropertyFindingOrigin.PLAINTEXT_SECRET)
    ]
    assert result.unreadable is False


def test_inline_key_material_reported_regardless_of_key_name(tmp_path: Path) -> None:
    key_file = tmp_path / "k.pem"
    write_pem_private_key(key_file, encrypted=False)
    inline = key_file.read_text(encoding="utf-8").replace("\n", "\\n")
    # 'note' is NOT a secret-named key, yet inline key material must be caught.
    props = _write(tmp_path / "app.properties", f"note={inline}\n")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [f.origin for f in result.findings] == [
        PropertyFindingOrigin.INLINE_KEY_MATERIAL
    ]


def test_referenced_unprotected_key_file_relative_to_properties_dir(
    tmp_path: Path,
) -> None:
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    write_pem_private_key(keys_dir / "server.key", encrypted=False)
    props = _write(tmp_path / "app.properties", "ssl.key.file=keys/server.key\n")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [f.origin for f in result.findings] == [
        PropertyFindingOrigin.REFERENCED_KEY_FILE
    ]
    assert len(result.assessed_references) == 1
    referenced_path, _classification = result.assessed_references[0]
    assert referenced_path == (keys_dir / "server.key").resolve()


def test_referenced_key_outside_scope_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    write_pem_private_key(outside / "id_rsa", encrypted=False)
    scope_root = tmp_path / "project"
    scope_root.mkdir()
    props = _write(scope_root / "app.properties", "ssl.key.file=../outside/id_rsa\n")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(scope_root)
    )

    assert result.findings == ()
    assert result.assessed_references == ()


def test_missing_reference_is_skipped_gracefully(tmp_path: Path) -> None:
    props = _write(
        tmp_path / "app.properties", "ssl.key.file=keys/does-not-exist.key\n"
    )

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert result.findings == ()
    assert result.assessed_references == ()


def test_externalized_encrypted_and_empty_values_are_not_reported(
    tmp_path: Path,
) -> None:
    body = (
        "db.password=${DB_PASSWORD}\n"
        "api.secret=ENC(abc123==)\n"
        "cache.password=\n"
        "audit.password.min.length=8\n"
    )
    props = _write(tmp_path / "app.properties", body)

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert result.findings == ()


def test_unreadable_file_is_flagged(tmp_path: Path) -> None:
    missing = tmp_path / "nope.properties"

    result = inspect_properties_file(
        missing, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert result.unreadable is True
    assert result.findings == ()
