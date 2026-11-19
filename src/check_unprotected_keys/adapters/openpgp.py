"""Classify passphrase protection of an OpenPGP secret-key armor block.

Only version-4 RSA secret-key and secret-subkey packets are read, and only
far enough to reach the string-to-key usage octet (RFC 4880). Any other
shape is uncertain. The block is malformed unless one of its secret packets
is cleartext.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterator
from typing import Literal

from check_unprotected_keys.domain.classification import build_assessment
from check_unprotected_keys.domain.models import (
    ProtectionAssessment,
    ProtectionClassification,
)

_BEGIN_HEADERS = (
    "-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "-----BEGIN PGP SECRET KEY BLOCK-----",
)
_BEGIN_HEADER_BYTES = tuple(header.encode("ascii") for header in _BEGIN_HEADERS)
_SECRET_PACKET_TAGS = frozenset({5, 7})
_RSA_ALGORITHMS = frozenset({1, 2, 3})
_RSA_PUBLIC_MPI_COUNT = 2
# Specifier size in octets, including the type byte.
# 0: hash. 1: hash + 8-octet salt. 3: hash + salt + count.
_S2K_SPECIFIER_LENGTH = {0: 2, 1: 10, 3: 11}
_CRC24_INIT = 0xB704CE
_CRC24_POLY = 0x1864CFB
_FORMAT_HINT = "openpgp"

SecretState = Literal["cleartext", "encrypted", "uncertain"]


def matches_private_key_block(blob: bytes) -> bool:
    """Return whether ``blob`` starts an OpenPGP secret-key armor block."""

    return blob.startswith(_BEGIN_HEADER_BYTES)


def inspect_private_key_block(payload: bytes) -> ProtectionAssessment:
    """Classify passphrase protection of one OpenPGP secret-key armor block."""

    try:
        states = _secret_states(_decode_armor(payload))
    except (ValueError, UnicodeError, binascii.Error):
        return _malformed()
    return _assess_states(states)


def _assess_states(states: list[SecretState]) -> ProtectionAssessment:
    # Protected outranks malformed in select_file_assessment. Using that
    # rank here would hide a packet whose protection could not be read.
    if "cleartext" in states:
        return _assessment(
            ProtectionClassification.UNPROTECTED,
            "OpenPGP private key is not protected.",
        )
    if states and "uncertain" not in states:
        return _assessment(
            ProtectionClassification.PROTECTED_WITH_PASSPHRASE,
            "OpenPGP private key is protected with a passphrase.",
        )
    return _malformed()


def _assessment(
    classification: ProtectionClassification,
    message: str,
) -> ProtectionAssessment:
    return build_assessment(
        classification,
        format_hint=_FORMAT_HINT,
        message=message,
    )


def _malformed() -> ProtectionAssessment:
    return _assessment(
        ProtectionClassification.MALFORMED,
        "OpenPGP private key could not be parsed.",
    )


def _decode_armor(payload: bytes) -> bytes:
    lines = payload.decode("ascii").splitlines()
    if not lines or lines[0] not in _BEGIN_HEADERS:
        raise ValueError("armor header is missing")
    try:
        separator = lines.index("")
    except ValueError as exc:
        raise ValueError("armor header separator is missing") from exc

    body: list[str] = []
    checksum: str | None = None
    saw_end = False
    for line in lines[separator + 1 :]:
        if line.startswith("-----END "):
            saw_end = True
            break
        if checksum is not None:
            raise ValueError("armor has data after the checksum")
        if line.startswith("="):
            checksum = line[1:].strip()
            continue
        if line:
            body.append(line)
    if not saw_end:
        raise ValueError("armor end is missing")

    raw = base64.b64decode("".join(body), validate=True)
    if checksum is not None and not _checksum_matches(raw, checksum):
        raise ValueError("armor checksum does not match")
    return raw


def _checksum_matches(raw: bytes, checksum: str) -> bool:
    try:
        expected = base64.b64decode(checksum, validate=True)
    except binascii.Error:
        return False
    return expected == _crc24(raw).to_bytes(3, "big")


def _crc24(data: bytes) -> int:
    """Return the RFC 4880 section 6.1 CRC-24 of ``data``."""

    crc = _CRC24_INIT
    for octet in data:
        crc ^= octet << 16
        for _bit in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= _CRC24_POLY
    return crc & 0xFFFFFF


def _secret_states(raw: bytes) -> list[SecretState]:
    return [
        _secret_packet_state(body)
        for tag, body in _iter_packets(raw)
        if tag in _SECRET_PACKET_TAGS
    ]


def _iter_packets(data: bytes) -> Iterator[tuple[int, bytes]]:
    offset = 0
    total = len(data)
    while offset < total:
        ctb = data[offset]
        offset += 1
        if ctb & 0xC0 != 0xC0:
            raise ValueError("packet header is not new-format")
        tag = ctb & 0x3F
        if offset >= total:
            raise ValueError("packet length is truncated")
        length, offset = _read_packet_length(data, offset)
        end = offset + length
        if end > total:
            raise ValueError("packet extends past the armor body")
        yield tag, data[offset:end]
        offset = end


def _read_packet_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 192:
        return first, offset
    if first < 224:
        if offset >= len(data):
            raise ValueError("packet length is truncated")
        second = data[offset]
        length = ((first - 192) << 8) + second + 192
        return length, offset + 1
    if first == 255:
        end = offset + 4
        if end > len(data):
            raise ValueError("packet length is truncated")
        return int.from_bytes(data[offset:end], "big"), end
    raise ValueError("partial packet length is not supported")


def _secret_packet_state(body: bytes) -> SecretState:
    if len(body) < 6 or body[0] != 4 or body[5] not in _RSA_ALGORITHMS:
        return "uncertain"
    try:
        offset = _skip_public_mpis(body, 6)
    except ValueError:
        return "uncertain"
    return _usage_state(body, offset)


def _skip_public_mpis(body: bytes, offset: int) -> int:
    for _mpi_index in range(_RSA_PUBLIC_MPI_COUNT):
        offset = _skip_mpi(body, offset)
    return offset


def _skip_mpi(body: bytes, offset: int) -> int:
    if offset + 2 > len(body):
        raise ValueError("mpi header is truncated")
    bits = int.from_bytes(body[offset : offset + 2], "big")
    end = offset + 2 + (bits + 7) // 8
    if end > len(body):
        raise ValueError("mpi extends past the packet")
    return end


def _usage_state(body: bytes, offset: int) -> SecretState:
    if offset >= len(body):
        return "uncertain"
    usage = body[offset]
    specifier_at = offset + 2
    if usage == 0:
        if offset + 1 < len(body):
            return "cleartext"
        return "uncertain"
    if usage not in (254, 255) or specifier_at >= len(body):
        return "uncertain"
    specifier_length = _S2K_SPECIFIER_LENGTH.get(body[specifier_at])
    if specifier_length is None or specifier_at + specifier_length > len(body):
        return "uncertain"
    return "encrypted"
