"""Tests for i18n / message-bundle handling (FR-015)."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unprotected_keys.adapters.properties_inspector import (
    PropertyFindingOrigin,
    inspect_properties_file,
)
from check_unprotected_keys.domain.models import EffectiveScope
from check_unprotected_keys.domain.properties import is_message_bundle

from ..support.fixture_builders import write_pem_private_key

_PATTERNS = ("password", "secret", "private", "key", "token", "pwd", "pass")


@pytest.mark.parametrize(
    "filename",
    [
        "messages.properties",
        "messages_es.properties",
        "messages_en_US.properties",
        "ApplicationResources_fr_CA.properties",
        "labels_de.properties",
        "ValidationMessages.properties",
        "messages_zh_Hant_TW.properties",
        "customtext_pt.properties",  # arbitrary base + unambiguous locale
        "app_es.properties",
    ],
)
def test_message_bundles_are_detected(filename: str) -> None:
    assert is_message_bundle(filename) is True


@pytest.mark.parametrize(
    "filename",
    [
        "application.properties",
        "app.properties",
        "config.properties",
        "db_password.properties",
        "service_url.properties",
        "application-prod.properties",  # Spring profile (hyphen), not a locale
        "connection_id.properties",  # collision code + non-bundle base → scanned
        "feature_no.properties",  # collision code + non-bundle base → scanned
    ],
)
def test_non_bundles_are_not_detected(filename: str) -> None:
    assert is_message_bundle(filename) is False


def _scope(root: Path) -> EffectiveScope:
    resolved = root.resolve()
    return EffectiveScope(
        root_directories=(resolved,),
        filename_patterns=("*.properties",),
        canonical_root_set=frozenset({resolved}),
    )


def test_message_bundle_prose_is_not_reported(tmp_path: Path) -> None:
    props = tmp_path / "messages_es.properties"
    props.write_text(
        "error.password.invalid=La contrasena introducida no es valida\n"
        "user.secret.question=Cual es tu pregunta secreta\n"
        "api.key.help=Introduce tu clave de API para continuar\n",
        encoding="utf-8",
    )

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert result.findings == ()


def test_real_signature_in_message_bundle_is_still_reported(tmp_path: Path) -> None:
    # Recall safety: the unconditional value-signature layer still applies.
    props = tmp_path / "messages_es.properties"
    props.write_text("aws.note=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [f.origin for f in result.findings] == [
        PropertyFindingOrigin.VALUE_SIGNATURE
    ]


def test_inline_key_material_in_message_bundle_is_still_reported(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "k.pem"
    write_pem_private_key(key_file, encrypted=False)
    inline = key_file.read_text(encoding="utf-8").replace("\n", "\\n")
    key_file.unlink()
    props = tmp_path / "messages_de.properties"
    props.write_text(f"sample.key={inline}\n", encoding="utf-8")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [f.origin for f in result.findings] == [
        PropertyFindingOrigin.INLINE_KEY_MATERIAL
    ]


def test_plaintext_secret_in_non_bundle_still_reported(tmp_path: Path) -> None:
    # A real config file (not a bundle) keeps the name-gated gate.
    props = tmp_path / "application.properties"
    props.write_text("db.password=hunter2xyz\n", encoding="utf-8")

    result = inspect_properties_file(
        props, name_patterns=_PATTERNS, scope=_scope(tmp_path)
    )

    assert [f.property_key for f in result.findings] == ["db.password"]
