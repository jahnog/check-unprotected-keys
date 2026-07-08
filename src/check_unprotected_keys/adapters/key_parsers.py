"""Parse supported key formats and classify protection state.

Key formats are dispatched through the ordered ``KEY_RECOGNIZERS`` registry
(spec 010 FR-004): adding a format means appending one ``KeyRecognizer`` —
no existing recognizer or dispatch code is edited. First match wins, so the
tuple order is the documented precedence
(specs/010-code-quality-audit/contracts/extension-points.md).
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from dataclasses import dataclass
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
CERTIFICATE_HEADER = b"-----BEGIN CERTIFICATE-----"
OPENSSH_PUBLIC_KEY_PREFIXES = (b"ssh-", b"ecdsa-", b"sk-")


def inspect_candidate_file(candidate_path: Path) -> ProtectionAssessment:
    """Classify the protection state of supported key material in one file."""

    try:
        payload = candidate_path.read_bytes()
    except OSError as exc:
        return build_assessment(
            ProtectionClassification.UNREADABLE,
            format_hint="filesystem",
            message=f"It was not possible to read the file: {type(exc).__name__}",
        )

    assessments = _collect_assessments(payload)
    if not assessments:
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="unknown",
            message=f"No private keys were detected in {candidate_path.name}.",
        )
    return select_file_assessment(assessments)


def inspect_text_for_key_material(text: str) -> ProtectionAssessment | None:
    """Return the strongest key-material assessment embedded in ``text``.

    Used to assess inline key material carried in a ``.properties`` value
    (FR-006). Returns ``None`` when the text contains no recognizable key
    material, so the caller can fall through to other value heuristics. Reuses
    the same blob-collection and selection logic as file inspection (DRY).
    """

    # str -> UTF-8 is lossless except for lone surrogates; "replace" only
    # guards that pathological case and cannot corrupt real key material.
    assessments = _collect_assessments(text.encode("utf-8", errors="replace"))
    if not assessments:
        return None
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


@dataclass(frozen=True, slots=True)
class KeyRecognizer:
    """One registered key format: a match predicate plus its inspector."""

    name: str
    matches: Callable[[bytes], bool]
    inspect: Callable[[bytes], ProtectionAssessment]


def _inspect_certificate(payload: bytes) -> ProtectionAssessment:
    return build_assessment(
        ProtectionClassification.PUBLIC_ONLY,
        format_hint="pem",
        message="File contains only certificate (public) material.",
    )


def _inspect_key_blob(payload: bytes) -> ProtectionAssessment | None:
    stripped = payload.strip()
    if not stripped:
        return None

    for recognizer in KEY_RECOGNIZERS:
        if recognizer.matches(stripped):
            return recognizer.inspect(stripped)

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
    try:
        text = payload.decode("utf-8")
        lossy = False
    except UnicodeDecodeError:
        # Replacement characters may corrupt the very header we classify on;
        # a lossy decode must never produce a confident MALFORMED (FR-012).
        text = payload.decode("utf-8", errors="replace")
        lossy = True
    encryption_line = next(
        (line for line in text.splitlines() if line.startswith("Encryption:")),
        None,
    )
    if encryption_line is None:
        if lossy:
            return build_assessment(
                ProtectionClassification.UNREADABLE,
                format_hint="putty",
                message=(
                    "PuTTY private key bytes could not be decoded "
                    "(undecodable-content); protection state is uncertain."
                ),
                reason="undecodable-content",
            )
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


# Ordered registry: first `matches` wins. Order mirrors the historical
# dispatch precedence exactly; append new formats unless one must shadow a
# broader prefix (contracts/extension-points.md).
KEY_RECOGNIZERS: tuple[KeyRecognizer, ...] = (
    KeyRecognizer(
        name="putty",
        matches=lambda blob: blob.startswith(b"PuTTY-User-Key-File-"),
        inspect=_inspect_putty_private_key,
    ),
    KeyRecognizer(
        name="openssh-private",
        matches=lambda blob: blob.startswith(OPENSSH_PRIVATE_KEY_HEADER),
        inspect=_inspect_openssh_private_key,
    ),
    KeyRecognizer(
        name="pem-private",
        matches=lambda blob: blob.startswith(PEM_PRIVATE_KEY_HEADERS),
        inspect=_inspect_pem_private_key,
    ),
    KeyRecognizer(
        name="pem-public",
        matches=lambda blob: blob.startswith(PEM_PUBLIC_KEY_HEADERS),
        inspect=_inspect_pem_public_key,
    ),
    KeyRecognizer(
        name="openssh-public",
        matches=lambda blob: blob.startswith(OPENSSH_PUBLIC_KEY_PREFIXES),
        inspect=_inspect_openssh_public_key,
    ),
    KeyRecognizer(
        name="certificate",
        matches=lambda blob: blob.startswith(CERTIFICATE_HEADER),
        inspect=_inspect_certificate,
    ),
)
