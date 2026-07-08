"""Dedicated characterization tests for key-format parsing (spec 010 FR-008).

Written against the current implementation BEFORE any refactor so the
key-recognizer registry change (WI-6) is provably behavior-preserving.
"""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.key_parsers import (
    inspect_candidate_file,
    inspect_text_for_key_material,
)
from check_unprotected_keys.domain.models import ProtectionClassification

from ..support.fixture_builders import (
    write_openssh_private_key,
    write_pem_private_key,
    write_public_key,
    write_putty_private_key,
)


def _classify(path: Path) -> ProtectionClassification:
    return inspect_candidate_file(path).classification


# ---------------------------------------------------------------------------
# PEM private keys
# ---------------------------------------------------------------------------


def test_pem_private_key_unprotected(tmp_path: Path) -> None:
    path = tmp_path / "server.pem"
    write_pem_private_key(path, encrypted=False)
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert assessment.format_hint == "pem"


def test_pem_private_key_encrypted(tmp_path: Path) -> None:
    path = tmp_path / "server.pem"
    write_pem_private_key(path, encrypted=True)
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


def test_pem_private_key_malformed_body(tmp_path: Path) -> None:
    path = tmp_path / "broken.pem"
    path.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nnot base64 at all\n"
        "-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_pem_private_key_truncated(tmp_path: Path) -> None:
    source = tmp_path / "full.pem"
    write_pem_private_key(source, encrypted=False)
    truncated = tmp_path / "truncated.pem"
    payload = source.read_bytes()
    truncated.write_bytes(payload[: len(payload) // 2])
    assert _classify(truncated) == ProtectionClassification.MALFORMED


# ---------------------------------------------------------------------------
# OpenSSH private keys
# ---------------------------------------------------------------------------


def test_openssh_private_key_unprotected(tmp_path: Path) -> None:
    path = tmp_path / "id_ed25519"
    write_openssh_private_key(path, encrypted=False)
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert assessment.format_hint == "openssh"


def test_openssh_private_key_encrypted(tmp_path: Path) -> None:
    path = tmp_path / "id_ed25519"
    write_openssh_private_key(path, encrypted=True)
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


def test_openssh_private_key_invalid_base64(tmp_path: Path) -> None:
    path = tmp_path / "id_ed25519"
    path.write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\n!!!not-base64!!!\n"
        "-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_openssh_private_key_missing_magic_prefix(tmp_path: Path) -> None:
    path = tmp_path / "id_ed25519"
    path.write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\ncGxhaW4td3JvbmctcHJlZml4\n"
        "-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_openssh_private_key_truncated_header_lines(tmp_path: Path) -> None:
    path = tmp_path / "id_ed25519"
    path.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_openssh_private_key_truncated_body(tmp_path: Path) -> None:
    source = tmp_path / "full"
    write_openssh_private_key(source, encrypted=False)
    lines = source.read_bytes().splitlines()
    truncated = tmp_path / "id_truncated"
    # Keep the BEGIN header and the first body line only: still base64, but the
    # binary payload is cut short.
    truncated.write_bytes(b"\n".join(lines[:2] + [lines[-1]]) + b"\n")
    assert _classify(truncated) == ProtectionClassification.MALFORMED


# ---------------------------------------------------------------------------
# PuTTY private keys
# ---------------------------------------------------------------------------


def test_putty_private_key_unprotected(tmp_path: Path) -> None:
    path = tmp_path / "workstation.ppk"
    write_putty_private_key(path, encrypted=False)
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert assessment.format_hint == "putty"


def test_putty_private_key_encrypted(tmp_path: Path) -> None:
    path = tmp_path / "workstation.ppk"
    write_putty_private_key(path, encrypted=True)
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


def test_putty_private_key_missing_encryption_header(tmp_path: Path) -> None:
    path = tmp_path / "workstation.ppk"
    path.write_text(
        "PuTTY-User-Key-File-3: ssh-ed25519\nComment: test-key\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_putty_private_key_empty_encryption_value_is_unprotected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "workstation.ppk"
    path.write_text(
        "PuTTY-User-Key-File-3: ssh-ed25519\nEncryption:\nComment: test-key\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.UNPROTECTED


# ---------------------------------------------------------------------------
# Public-only and certificate material
# ---------------------------------------------------------------------------


def test_openssh_public_key_is_public_only(tmp_path: Path) -> None:
    path = tmp_path / "id_rsa.pub"
    write_public_key(path)
    assert _classify(path) == ProtectionClassification.PUBLIC_ONLY


def test_openssh_public_key_malformed(tmp_path: Path) -> None:
    path = tmp_path / "id_rsa.pub"
    path.write_text("ssh-rsa not!valid!base64 comment\n", encoding="utf-8")
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_pem_public_key_malformed(tmp_path: Path) -> None:
    path = tmp_path / "pub.pem"
    path.write_text(
        "-----BEGIN PUBLIC KEY-----\ngarbage\n-----END PUBLIC KEY-----\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_certificate_is_public_only(tmp_path: Path) -> None:
    path = tmp_path / "tls.crt"
    path.write_text(
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    assert _classify(path) == ProtectionClassification.PUBLIC_ONLY


# ---------------------------------------------------------------------------
# File-level dispatch, embedded blocks, unreadable files
# ---------------------------------------------------------------------------


def test_unrecognized_content_is_malformed(tmp_path: Path) -> None:
    path = tmp_path / "notes.key"
    path.write_text("nothing key-like in here\n", encoding="utf-8")
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.MALFORMED
    assert "No private keys were detected" in assessment.message


def test_embedded_pem_block_inside_config_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "key.pem"
    write_pem_private_key(source, encrypted=False)
    embedded = tmp_path / "service.env"
    embedded.write_text(
        "# header noise\n" + source.read_text(encoding="utf-8") + "# trailer\n",
        encoding="utf-8",
    )
    assert _classify(embedded) == ProtectionClassification.UNPROTECTED


def test_unreadable_file_classifies_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "blocked.pem"
    write_pem_private_key(path, encrypted=False)
    path.chmod(0)
    try:
        assessment = inspect_candidate_file(path)
    finally:
        path.chmod(0o600)
    assert assessment.classification == ProtectionClassification.UNREADABLE
    assert assessment.format_hint == "filesystem"


# ---------------------------------------------------------------------------
# Inline text inspection (properties values)
# ---------------------------------------------------------------------------


def test_inline_text_without_key_material_returns_none() -> None:
    assert inspect_text_for_key_material("plain value, no keys") is None


def test_inline_text_with_unprotected_pem_detected(tmp_path: Path) -> None:
    source = tmp_path / "key.pem"
    write_pem_private_key(source, encrypted=False)
    assessment = inspect_text_for_key_material(source.read_text(encoding="utf-8"))
    assert assessment is not None
    assert assessment.classification == ProtectionClassification.UNPROTECTED


def test_inline_text_with_certificate_is_public_only() -> None:
    assessment = inspect_text_for_key_material(
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----"
    )
    assert assessment is not None
    assert assessment.classification == ProtectionClassification.PUBLIC_ONLY


# ---------------------------------------------------------------------------
# Lossy-decode honesty (spec 010 FR-012 / A5)
# ---------------------------------------------------------------------------


def test_lossy_putty_without_encryption_header_is_not_malformed(
    tmp_path: Path,
) -> None:
    """Invalid UTF-8 that corrupts the header region must classify as an
    uncertain/unreadable result, never as a confident MALFORMED "no finding".
    """

    path = tmp_path / "corrupt.ppk"
    path.write_bytes(b"PuTTY-User-Key-File-3: ssh-ed25519\n\xff\xfe\x9c broken bytes\n")
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.UNREADABLE
    assert "undecodable-content" in assessment.message
    assert assessment.reason == "undecodable-content"


def test_lossy_putty_with_intact_encryption_header_still_classified(
    tmp_path: Path,
) -> None:
    """A decodable Encryption header keeps its honest classification even when
    other bytes in the file are invalid UTF-8.
    """

    path = tmp_path / "mixed.ppk"
    path.write_bytes(
        b"PuTTY-User-Key-File-3: ssh-ed25519\n"
        b"Encryption: none\n"
        b"Comment: \xff\xfe invalid utf-8 comment\n"
    )
    assert _classify(path) == ProtectionClassification.UNPROTECTED
