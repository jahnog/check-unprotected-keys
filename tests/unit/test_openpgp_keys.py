"""OpenPGP armored secret-key protection classification."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from check_unprotected_keys.adapters.key_parsers import inspect_candidate_file
from check_unprotected_keys.adapters.openpgp import _crc24, inspect_private_key_block
from check_unprotected_keys.domain.models import ProtectionClassification

from ..support.fixture_builders import write_pem_private_key

_PRIVATE_HEADER = "-----BEGIN PGP PRIVATE KEY BLOCK-----"
_SECRET_HEADER = "-----BEGIN PGP SECRET KEY BLOCK-----"
_RFC4880_ARMOR_BODY = (
    "yDgBO22WxBHv7O8X7O/jygAEzol56iUKiXmV+XmpCtmpqQUKiQrFqclFqUDBovzSvBSFjNSiVHsuAA=="
)
_USAGE_SHA1 = 254
_USAGE_CHECKSUM = 255
_CIPHER_AES256 = 9
_S2K_ITERATED = 3
_HASH_SHA256 = 8


def _classify(path: Path) -> ProtectionClassification:
    return inspect_candidate_file(path).classification


def _mpi(value: int) -> bytes:
    byte_length = (value.bit_length() + 7) // 8
    return value.bit_length().to_bytes(2, "big") + value.to_bytes(byte_length, "big")


def _rsa_secret_body(usage: int, tail: bytes) -> bytes:
    return bytes([4, 0, 0, 0, 0, 1]) + _mpi(65537) + _mpi(65537) + bytes([usage]) + tail


def _packet(tag: int, body: bytes) -> bytes:
    length = len(body)
    marker = 0xC0 | tag
    if length < 192:
        header = bytes([marker, length])
    elif length < 8384:
        adjusted = length - 192
        header = bytes([marker, (adjusted >> 8) + 192, adjusted & 0xFF])
    else:
        header = bytes([marker, 255]) + length.to_bytes(4, "big")
    return header + body


def _old_packet(tag: int, body: bytes, *, length_octets: int | None = None) -> bytes:
    """Build an RFC 4880 old-format packet.

    ``length_octets`` forces the length field width. GnuPG picks the shortest
    definite field that fits; pass 4 to exercise a four-octet header on a
    small body.
    """

    length = len(body)
    if length_octets is None:
        if length < 256:
            length_octets = 1
        elif length < 65536:
            length_octets = 2
        else:
            length_octets = 4
    length_type = {1: 0, 2: 1, 4: 2}[length_octets]
    marker = 0x80 | (tag << 2) | length_type
    return bytes([marker]) + length.to_bytes(length_octets, "big") + body


def _iterated_s2k_tail(*, extra: bytes = b"") -> bytes:
    return (
        bytes([_CIPHER_AES256, _S2K_ITERATED, _HASH_SHA256])
        + (b"\x11" * 8)
        + bytes([0x60])
        + extra
    )


def _encrypted_packet(*, usage: int = _USAGE_SHA1) -> bytes:
    # Pad past 191 octets so the packet uses a two-octet length, as real
    # 2048-bit secret packets do.
    body = _rsa_secret_body(usage, _iterated_s2k_tail(extra=b"\x22" * 180))
    return _packet(5, body)


def _armor(
    packets: bytes,
    *,
    begin: str = _PRIVATE_HEADER,
    valid_crc: bool = True,
) -> bytes:
    encoded = base64.b64encode(packets).decode("ascii")
    wrapped = [encoded[index : index + 64] for index in range(0, len(encoded), 64)]
    checksum = base64.b64encode(_crc24(packets).to_bytes(3, "big")).decode("ascii")
    if not valid_crc:
        checksum = ("A" if checksum[0] != "A" else "B") + checksum[1:]
    end = begin.replace("BEGIN", "END")
    return "\n".join([begin, "", *wrapped, f"={checksum}", end, ""]).encode("ascii")


def _write(tmp_path: Path, name: str, payload: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def test_crc24_matches_rfc4880_armor_sample() -> None:
    raw = base64.b64decode(_RFC4880_ARMOR_BODY)
    checksum = base64.b64encode(_crc24(raw).to_bytes(3, "big")).decode("ascii")
    assert checksum == "njUN"


@pytest.mark.parametrize("begin", [_PRIVATE_HEADER, _SECRET_HEADER])
@pytest.mark.parametrize("usage", [_USAGE_SHA1, _USAGE_CHECKSUM])
def test_encrypted_v4_rsa_secret_key_is_protected(
    tmp_path: Path, begin: str, usage: int
) -> None:
    path = _write(
        tmp_path,
        "secret.asc",
        _armor(_encrypted_packet(usage=usage), begin=begin),
    )
    assessment = inspect_candidate_file(path)
    assert (
        assessment.classification == ProtectionClassification.PROTECTED_WITH_PASSPHRASE
    )
    assert assessment.format_hint == "openpgp"
    assert assessment.message == "OpenPGP private key is protected with a passphrase."


def test_cleartext_v4_rsa_secret_key_is_unprotected(tmp_path: Path) -> None:
    packet = _packet(5, _rsa_secret_body(0, b"\x01\x02\x03"))
    path = _write(tmp_path, "secret.asc", _armor(packet))
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.UNPROTECTED
    assert assessment.message == "OpenPGP private key is not protected."


def test_old_format_encrypted_v4_rsa_secret_key_is_protected(tmp_path: Path) -> None:
    # Pad past 255 octets so the old-format header uses a two-octet length,
    # matching GnuPG secret-key exports such as a 2048-bit RSA packet.
    body = _rsa_secret_body(_USAGE_SHA1, _iterated_s2k_tail(extra=b"\x22" * 240))
    assert 256 <= len(body) < 65536
    path = _write(tmp_path, "secret.asc", _armor(_old_packet(5, body)))
    assessment = inspect_candidate_file(path)
    assert (
        assessment.classification == ProtectionClassification.PROTECTED_WITH_PASSPHRASE
    )
    assert assessment.format_hint == "openpgp"
    assert assessment.message == "OpenPGP private key is protected with a passphrase."


def test_old_format_cleartext_v4_rsa_secret_key_is_unprotected(tmp_path: Path) -> None:
    body = _rsa_secret_body(0, b"\x01\x02\x03")
    assert len(body) < 256
    path = _write(tmp_path, "secret.asc", _armor(_old_packet(5, body)))
    assert _classify(path) == ProtectionClassification.UNPROTECTED


def test_old_format_four_octet_length_is_protected(tmp_path: Path) -> None:
    body = _rsa_secret_body(_USAGE_SHA1, _iterated_s2k_tail())
    path = _write(
        tmp_path,
        "secret.asc",
        _armor(_old_packet(5, body, length_octets=4)),
    )
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


def test_old_format_indeterminate_length_is_malformed(tmp_path: Path) -> None:
    # Tag 5 with length type 3. The following octet is not a length field.
    packet = bytes([0x80 | (5 << 2) | 3, 0x00])
    path = _write(tmp_path, "secret.asc", _armor(packet))
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_cleartext_packet_outranks_encrypted_packet(tmp_path: Path) -> None:
    packets = _encrypted_packet() + _packet(7, _rsa_secret_body(0, b"\x01\x02"))
    path = _write(tmp_path, "secret.asc", _armor(packets))
    assert _classify(path) == ProtectionClassification.UNPROTECTED


def test_unknown_s2k_type_is_malformed(tmp_path: Path) -> None:
    tail = bytes([_CIPHER_AES256, 101]) + (b"\x00" * 8)
    packet = _packet(5, _rsa_secret_body(_USAGE_SHA1, tail))
    path = _write(tmp_path, "secret.asc", _armor(packet))
    assessment = inspect_candidate_file(path)
    assert assessment.classification == ProtectionClassification.MALFORMED
    assert assessment.message == "OpenPGP private key could not be parsed."


def test_bad_armor_crc_is_malformed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "secret.asc",
        _armor(_encrypted_packet(), valid_crc=False),
    )
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_truncated_packet_is_malformed(tmp_path: Path) -> None:
    path = _write(tmp_path, "secret.asc", _armor(_encrypted_packet()[:10]))
    assert _classify(path) == ProtectionClassification.MALFORMED


def test_embedded_encrypted_block_is_protected(tmp_path: Path) -> None:
    payload = b"preamble\n" + _armor(_encrypted_packet()) + b"\ntrailer\n"
    path = _write(tmp_path, "notes.txt", payload)
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


def test_unprotected_pem_block_outranks_encrypted_openpgp(tmp_path: Path) -> None:
    pem_path = tmp_path / "clear.pem"
    write_pem_private_key(pem_path, encrypted=False)
    payload = (
        b"preamble\n" + _armor(_encrypted_packet()) + b"\n" + pem_path.read_bytes()
    )
    path = _write(tmp_path, "notes.txt", payload)
    assert _classify(path) == ProtectionClassification.UNPROTECTED


def test_five_octet_length_cleartext_is_unprotected(tmp_path: Path) -> None:
    body = _rsa_secret_body(0, b"\x01" + (b"\x00" * 8400))
    assert len(body) >= 8384
    path = _write(tmp_path, "secret.asc", _armor(_packet(5, body)))
    assert _classify(path) == ProtectionClassification.UNPROTECTED


def test_blank_body_line_is_ignored(tmp_path: Path) -> None:
    text = _armor(_encrypted_packet()).decode("ascii").replace("\n\n", "\n\n\n", 1)
    path = _write(tmp_path, "secret.asc", text.encode("ascii"))
    assert _classify(path) == ProtectionClassification.PROTECTED_WITH_PASSPHRASE


@pytest.mark.parametrize(
    "packets",
    [
        b"\x94\x01\x00",
        b"\x01\x00",
        bytes([0x80 | (5 << 2) | 1]),
        bytes([0xC5, 224]),
        bytes([0xC5]),
        bytes([0xC5, 192]),
        bytes([0xC5, 255, 0, 0]),
        _packet(5, bytes([4, 0, 0, 0, 0, 22]) + (b"\x00" * 8)),
        _packet(5, bytes([4, 0, 0, 0, 0, 1, 0x00])),
        _packet(5, bytes([4, 0, 0, 0, 0, 1, 0xFF, 0xFF])),
        _packet(5, bytes([4, 0, 0, 0, 0, 1]) + _mpi(65537) + _mpi(65537)),
        _packet(5, _rsa_secret_body(0, b"")),
        _packet(5, _rsa_secret_body(9, b"\x03\x08" + (b"\x11" * 8) + b"\x60")),
        _packet(
            5,
            _rsa_secret_body(_USAGE_SHA1, bytes([_CIPHER_AES256, _S2K_ITERATED])),
        ),
    ],
)
def test_unclassifiable_packet_is_malformed(tmp_path: Path, packets: bytes) -> None:
    path = _write(tmp_path, "secret.asc", _armor(packets))
    assert _classify(path) == ProtectionClassification.MALFORMED


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"-----BEGIN PGP PRIVATE KEY BLOCK----- junk\n",
        (
            b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            b"YWJj\n"
            b"-----END PGP PRIVATE KEY BLOCK-----\n"
        ),
        b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n\nYWJj\n",
        (
            b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            b"\nYWJj\n=****\n"
            b"-----END PGP PRIVATE KEY BLOCK-----\n"
        ),
        (
            b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            b"\nYWJj\n=njUN\nextra\n"
            b"-----END PGP PRIVATE KEY BLOCK-----\n"
        ),
    ],
)
def test_broken_armor_is_malformed(payload: bytes) -> None:
    assessment = inspect_private_key_block(payload)
    assert assessment.classification == ProtectionClassification.MALFORMED
