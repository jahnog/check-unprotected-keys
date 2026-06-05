"""Unit tests for supported key protection classification."""

from __future__ import annotations

import stat
from pathlib import Path

from find_unencrypted_keys.adapters.key_parsers import inspect_candidate_file
from find_unencrypted_keys.domain.classification import is_finding
from find_unencrypted_keys.domain.models import ProtectionClassification

from ..support.fixture_builders import (
    write_openssh_private_key,
    write_pem_private_key,
    write_public_key,
    write_putty_private_key,
)


def test_unencrypted_pem_private_key_is_reported_as_finding(tmp_path: Path) -> None:
    candidate = tmp_path / "id_rsa"
    write_pem_private_key(candidate, encrypted=False)

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert is_finding(assessment)


def test_encrypted_pem_private_key_is_not_reported(tmp_path: Path) -> None:
    candidate = tmp_path / "service_private.pem"
    write_pem_private_key(candidate, encrypted=True)

    assessment = inspect_candidate_file(candidate)

    assert (
        assessment.classification == ProtectionClassification.PROTECTED_WITH_PASSPHRASE
    )
    assert not is_finding(assessment)


def test_unencrypted_openssh_private_key_is_reported_as_finding(tmp_path: Path) -> None:
    candidate = tmp_path / "id_ed25519"
    write_openssh_private_key(candidate, encrypted=False)

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert is_finding(assessment)


def test_encrypted_openssh_private_key_is_not_reported(tmp_path: Path) -> None:
    candidate = tmp_path / "id_ed25519"
    write_openssh_private_key(candidate, encrypted=True)

    assessment = inspect_candidate_file(candidate)

    assert (
        assessment.classification == ProtectionClassification.PROTECTED_WITH_PASSPHRASE
    )
    assert not is_finding(assessment)


def test_unencrypted_putty_private_key_is_reported_as_finding(tmp_path: Path) -> None:
    candidate = tmp_path / "desktop.ppk"
    write_putty_private_key(candidate, encrypted=False)

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert is_finding(assessment)


def test_encrypted_putty_private_key_is_not_reported(tmp_path: Path) -> None:
    candidate = tmp_path / "desktop.ppk"
    write_putty_private_key(candidate, encrypted=True)

    assessment = inspect_candidate_file(candidate)

    assert (
        assessment.classification == ProtectionClassification.PROTECTED_WITH_PASSPHRASE
    )
    assert not is_finding(assessment)


def test_public_key_file_is_classified_as_public_only(tmp_path: Path) -> None:
    candidate = tmp_path / "id_rsa.pub"
    write_public_key(candidate)

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.PUBLIC_ONLY
    assert not is_finding(assessment)


def test_embedded_private_key_block_is_detected_inside_env_file(tmp_path: Path) -> None:
    source_key = tmp_path / "service_private.pem"
    write_pem_private_key(source_key, encrypted=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        'PRIVATE_KEY="""\n' + source_key.read_text(encoding="utf-8") + '"""\n',
        encoding="utf-8",
    )

    assessment = inspect_candidate_file(env_file)

    assert assessment.classification == ProtectionClassification.UNPROTECTED


def test_unreadable_file_is_classified_as_unreadable(tmp_path: Path) -> None:
    candidate = tmp_path / "blocked_private.pem"
    write_pem_private_key(candidate, encrypted=False)
    candidate.chmod(0)

    try:
        assessment = inspect_candidate_file(candidate)
    finally:
        candidate.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert assessment.classification == ProtectionClassification.UNREADABLE


def test_malformed_openssh_private_key_is_classified_as_malformed(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "id_ed25519"
    candidate.write_text(
        (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "not-valid-base64\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        ),
        encoding="utf-8",
    )

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.MALFORMED


def test_putty_private_key_without_encryption_header_is_classified_as_malformed(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "desktop.ppk"
    candidate.write_text(
        "PuTTY-User-Key-File-3: ssh-ed25519\nComment: missing encryption\n",
        encoding="utf-8",
    )

    assessment = inspect_candidate_file(candidate)

    assert assessment.classification == ProtectionClassification.MALFORMED
