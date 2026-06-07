"""Parse supported key formats and classify protection state."""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization

from check_unprotected_keys.domain.classification import (
    build_assessment,
    select_file_assessment,
)
from check_unprotected_keys.domain.models import (
    ProtectionAssessment,
    ProtectionClassification,
)

PEM_BLOCK_PATTERN = re.compile(
    rb"-----BEGIN [A-Z0-9 ]+-----.*?-----END [A-Z0-9 ]+-----",
    re.DOTALL,
)
OPENSSH_PRIVATE_KEY_HEADER = b"-----BEGIN OPENSSH PRIVATE KEY-----"
PEM_PRIVATE_KEY_HEADERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN DSA PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
)
PEM_PUBLIC_KEY_HEADERS = (
    b"-----BEGIN PUBLIC KEY-----",
    b"-----BEGIN RSA PUBLIC KEY-----",
    b"-----BEGIN EC PUBLIC KEY-----",
)
OPENSSH_PUBLIC_KEY_PREFIXES = (b"ssh-", b"ecdsa-", b"sk-")


def inspect_candidate_file(candidate_path: Path) -> ProtectionAssessment:
    """Classify the protection state of supported key material in one file."""

    try:
        payload = candidate_path.read_bytes()
    except OSError as exc:
        return build_assessment(
            ProtectionClassification.UNREADABLE,
            format_hint="filesystem",
            message=f"{candidate_path.name} could not be read: {type(exc).__name__}",
        )

    assessments = _collect_assessments(payload)
    if not assessments:
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="unknown",
            message=f"{candidate_path.name} does not contain supported key material.",
        )
    return select_file_assessment(assessments)


def _collect_assessments(payload: bytes) -> list[ProtectionAssessment]:
    direct_assessment = _inspect_key_blob(payload)
    if direct_assessment is not None:
        return [direct_assessment]

    embedded_assessments = [
        assessment
        for block in PEM_BLOCK_PATTERN.findall(payload)
        if (assessment := _inspect_key_blob(block)) is not None
    ]
    return embedded_assessments


def _inspect_key_blob(payload: bytes) -> ProtectionAssessment | None:
    stripped = payload.strip()
    if not stripped:
        return None

    if stripped.startswith(b"PuTTY-User-Key-File-"):
        return _inspect_putty_private_key(stripped)

    if stripped.startswith(OPENSSH_PRIVATE_KEY_HEADER):
        return _inspect_openssh_private_key(stripped)

    if stripped.startswith(PEM_PRIVATE_KEY_HEADERS):
        return _inspect_pem_private_key(stripped)

    if stripped.startswith(PEM_PUBLIC_KEY_HEADERS):
        return _inspect_pem_public_key(stripped)

    if stripped.startswith(OPENSSH_PUBLIC_KEY_PREFIXES):
        return _inspect_openssh_public_key(stripped)

    return None


def _inspect_pem_private_key(payload: bytes) -> ProtectionAssessment:
    try:
        serialization.load_pem_private_key(payload, password=None)
    except TypeError:
        return build_assessment(
            ProtectionClassification.PROTECTED_WITH_PASSPHRASE,
            format_hint="pem",
            message="PEM private key is protected with a passphrase.",
        )
    except (ValueError, UnsupportedAlgorithm):
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="pem",
            message="PEM private key could not be parsed.",
        )

    return build_assessment(
        ProtectionClassification.UNPROTECTED,
        format_hint="pem",
        message="PEM private key is not protected.",
    )


def _inspect_pem_public_key(payload: bytes) -> ProtectionAssessment:
    try:
        serialization.load_pem_public_key(payload)
    except (ValueError, UnsupportedAlgorithm):
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="pem",
            message="PEM public key could not be parsed.",
        )

    return build_assessment(
        ProtectionClassification.PUBLIC_ONLY,
        format_hint="pem",
        message="PEM file contains only public key material.",
    )


def _inspect_openssh_private_key(payload: bytes) -> ProtectionAssessment:
    try:
        cipher_name, kdf_name = _parse_openssh_private_key_header(payload)
    except ValueError:
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="openssh",
            message="OpenSSH private key could not be parsed.",
        )

    if cipher_name != "none" or kdf_name != "none":
        return build_assessment(
            ProtectionClassification.PROTECTED_WITH_PASSPHRASE,
            format_hint="openssh",
            message="OpenSSH private key is protected with a passphrase.",
        )

    try:
        serialization.load_ssh_private_key(payload, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm):
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="openssh",
            message="OpenSSH private key could not be parsed.",
        )

    return build_assessment(
        ProtectionClassification.UNPROTECTED,
        format_hint="openssh",
        message="OpenSSH private key is not protected.",
    )


def _inspect_openssh_public_key(payload: bytes) -> ProtectionAssessment:
    try:
        serialization.load_ssh_public_key(payload)
    except (ValueError, UnsupportedAlgorithm):
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="openssh",
            message="OpenSSH public key could not be parsed.",
        )

    return build_assessment(
        ProtectionClassification.PUBLIC_ONLY,
        format_hint="openssh",
        message="File contains only public key material.",
    )


def _inspect_putty_private_key(payload: bytes) -> ProtectionAssessment:
    text = payload.decode("utf-8", errors="replace")
    encryption_line = next(
        (line for line in text.splitlines() if line.startswith("Encryption:")),
        None,
    )
    if encryption_line is None:
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="putty",
            message="PuTTY private key is missing an Encryption header.",
        )

    encryption_value = encryption_line.partition(":")[2].strip().lower()
    if encryption_value in {"", "none"}:
        return build_assessment(
            ProtectionClassification.UNPROTECTED,
            format_hint="putty",
            message="PuTTY private key is not protected.",
        )

    return build_assessment(
        ProtectionClassification.PROTECTED_WITH_PASSPHRASE,
        format_hint="putty",
        message="PuTTY private key is protected with a passphrase.",
    )


def _parse_openssh_private_key_header(payload: bytes) -> tuple[str, str]:
    lines = payload.splitlines()
    if len(lines) < 3:
        raise ValueError("OpenSSH private key is incomplete.")

    body_lines = [
        line.strip()
        for line in lines
        if line
        and not line.startswith(b"-----BEGIN")
        and not line.startswith(b"-----END")
    ]
    try:
        raw = base64.b64decode(b"".join(body_lines), validate=True)
    except binascii.Error as exc:
        raise ValueError("OpenSSH payload is not valid base64.") from exc

    prefix = b"openssh-key-v1\x00"
    if not raw.startswith(prefix):
        raise ValueError("OpenSSH private key prefix is missing.")

    offset = len(prefix)
    cipher_name, offset = _read_openssh_string(raw, offset)
    kdf_name, _ = _read_openssh_string(raw, offset)
    return cipher_name.decode("ascii"), kdf_name.decode("ascii")


def _read_openssh_string(payload: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(payload):
        raise ValueError("Missing OpenSSH string length.")

    length = int.from_bytes(payload[offset : offset + 4], byteorder="big")
    start = offset + 4
    end = start + length
    if end > len(payload):
        raise ValueError("OpenSSH string extends past payload length.")
    return payload[start:end], end
