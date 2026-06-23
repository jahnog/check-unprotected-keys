"""Pure parsing and secret heuristics for Java ``.properties`` content.

This module is I/O-free: it turns decoded text into property entries and
classifies values. Byte reading, key-file reference following, and reuse of the
key-material parser live in the adapter layer.

Detection is a layered, confidence-tiered classifier (feature 009):

1. Token-aware key matching (:func:`tokenize_key`, :func:`classify_key_tier`)
   replaces substring matching so container words like ``compass``/``tokenizer``
   no longer match.
2. Key-name strength tiers (:class:`KeyNameTier`) with qualifier demotion decide
   how much value evidence is required.
3. An unconditional value-signature layer (:func:`match_value_signature`) catches
   provider tokens, JWTs, embedded-credential URLs, and high-entropy blobs
   regardless of the key name.
4. Conservative, tier-aware value-shape and sample/mask exclusions
   (:func:`is_sample_placeholder`, :func:`is_non_secret_shape`) remove the
   benign-config false positives.
5. A tier-aware credential gate (:func:`is_credential_like`).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

_WHITESPACE = (" ", "\t", "\f")
_VALUE_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}

# Credential-likeness gates. STRONG keys keep the loose floor so word-like human
# passwords are caught; WEAK/ambiguous keys require random-secret-like evidence.
MIN_SECRET_LENGTH = 6
MIN_ENTROPY_BITS_PER_CHAR = 2.5
MIN_WEAK_LENGTH = 12
MIN_WEAK_ENTROPY = 3.0

# Generic high-entropy blob signature (name-independent). Tight enough to exclude
# ordinary identifiers and hashes while catching random base64/base64url secrets.
BLOB_MIN_LENGTH = 32
BLOB_MIN_ENTROPY = 4.0

# Value suffixes that signal a path to key material (used for PATH_LIKE).
_KEY_FILE_SUFFIXES = (".pem", ".key", ".ppk", ".p8", ".pk8", ".ovpn", ".tfvars")

# --- Key-name matching catalogs (research Decisions 1-2) ----------------------

# Long, low-collision patterns matched as a substring of a single key token.
_STRONG_SUBSTRING_PATTERNS = frozenset(
    {
        "password",
        "passwd",
        "passphrase",
        "credential",
        "credentials",
        "secret",
        "apikey",
        "privatekey",
        "secretkey",
        "accesskey",
        "clientsecret",
    }
)
# Short, high-collision patterns matched only as a whole key token.
_WEAK_TOKEN_PATTERNS = frozenset({"key", "keys", "token", "tokens", "private", "priv"})
# Tokens that mark the key as STRONG when matched whole.
_STRONG_TOKEN_PATTERNS = frozenset({"pass", "pwd"})

# When the token immediately after a matched secret token is one of these, the
# key denotes metadata *about* a secret, not the secret itself -> demote to WEAK.
_QUALIFIER_DENYLIST = frozenset(
    {
        "alias",
        "id",
        "name",
        "kind",
        "type",
        "algorithm",
        "alg",
        "store",
        "storetype",
        "provider",
        "header",
        "prefix",
        "suffix",
        "enabled",
        "disabled",
        "required",
        "optional",
        "length",
        "len",
        "size",
        "count",
        "max",
        "min",
        "ttl",
        "timeout",
        "interval",
        "expiry",
        "expiration",
        "rotation",
        "policy",
        "format",
        "encoding",
        "charset",
        "class",
        "classname",
        "strategy",
        "location",
        "path",
        "dir",
        "directory",
        "pattern",
        "regex",
        "serializer",
        "deserializer",
        "resolver",
        "url",
        "uri",
        "endpoint",
        "host",
        "port",
        "version",
        "mode",
        "label",
        "field",
        "column",
        "param",
        "attribute",
        "default",
        "example",
        "placeholder",
        "index",
        "order",
        "public",
        "file",
    }
)

# --- Value-shape exclusion catalogs (research Decisions 5-6) -------------------

# Documentation defaults / masks that are essentially never a live secret. Kept
# conservative: plausibly-real weak passwords (changeit, admin, secret123) are
# intentionally NOT listed, honouring the zero-false-negative priority.
_SAMPLE_VOCAB = frozenset(
    {
        "changeme",
        "change-me",
        "change_me",
        "replaceme",
        "your_password_here",
        "yourpasswordhere",
        "your-password",
        "your_password",
        "yourpassword",
        "your-secret",
        "your_secret",
        "yoursecret",
        "example",
        "sample",
        "dummy",
        "placeholder",
        "tbd",
        "todo",
        "fixme",
        "redacted",
        "none",
        "null",
        "nil",
        "na",
        "n/a",
        "notset",
        "not-set",
        "unset",
        "undefined",
    }
)
_SAMPLE_PATTERNS = (
    re.compile(r"^[xX]{4,}$"),
    re.compile(r"^\*{4,}$"),
    re.compile(r"^•{3,}$"),
    re.compile(r"^<[^>]+>$"),
    re.compile(r"^\[[^\]]+\]$"),
    re.compile(r"^\.{3,}$"),
)

# Algorithm / keystore / format constants (case-insensitive exact match).
_ALG_ENUM = frozenset(
    {
        "rs256",
        "rs384",
        "rs512",
        "hs256",
        "hs384",
        "hs512",
        "es256",
        "es384",
        "es512",
        "ps256",
        "ps384",
        "ps512",
        "pbkdf2",
        "pbkdf2withhmacsha256",
        "pbkdf2withhmacsha512",
        "hmacsha256",
        "hmacsha512",
        "sha-256",
        "sha-512",
        "sha256",
        "sha512",
        "md5",
        "aes",
        "aes128",
        "aes256",
        "aes-128",
        "aes-256",
        "rsa",
        "ec",
        "ecdsa",
        "ed25519",
        "dsa",
        "pkcs1",
        "pkcs8",
        "pkcs12",
        "jks",
        "jceks",
        "bcfks",
        "pem",
        "der",
        "x.509",
        "x509",
        "bcrypt",
        "scrypt",
        "argon2",
        "argon2id",
        "plain",
        "none",
        "noop",
    }
)

_DOTTED_ID = re.compile(r"^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)+$")
_SEMVER = re.compile(r"^v?\d+\.\d+(\.\d+)?([-+][0-9A-Za-z.-]+)?$")
_HEADER_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*(-[A-Z][A-Za-z0-9]*)+$")
_KEBAB_SNAKE = re.compile(r"^[A-Za-z][A-Za-z0-9]*([._\-][A-Za-z0-9]+)+$")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_HOSTNAME_DOTTED = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}))+$"
)
_DURATION = re.compile(
    r"^\d+(\.\d+)?\s?"
    r"(ms|s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|"
    r"hours|d|day|days|w|week|weeks|kb|mb|gb|tb|b)$",
    re.IGNORECASE,
)

# --- Value-signature catalog (research Decision 3) ----------------------------


class ValueSignature(StrEnum):
    """A recognized high-confidence credential format (name-independent)."""

    AWS_ACCESS_KEY = "aws-access-key"
    GITHUB_TOKEN = "github-token"
    GITLAB_TOKEN = "gitlab-token"
    SLACK_TOKEN = "slack-token"
    GOOGLE_API_KEY = "google-api-key"
    STRIPE_KEY = "stripe-key"
    TWILIO_KEY = "twilio-key"
    SENDGRID_KEY = "sendgrid-key"
    NPM_TOKEN = "npm-token"
    OPENAI_KEY = "openai-key"
    JWT = "jwt"
    EMBEDDED_CREDENTIAL_URL = "embedded-credential-url"
    HIGH_ENTROPY_BLOB = "high-entropy-blob"


_TOKEN_GUARD = r"(?<![A-Za-z0-9_])"
_SIGNATURE_PATTERNS: tuple[tuple[ValueSignature, re.Pattern[str]], ...] = (
    (
        ValueSignature.AWS_ACCESS_KEY,
        re.compile(
            _TOKEN_GUARD
            + r"(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[A-Z0-9]{16}"
        ),
    ),
    (
        ValueSignature.GITHUB_TOKEN,
        re.compile(
            _TOKEN_GUARD + r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[0-9A-Za-z_]{82})"
        ),
    ),
    (
        ValueSignature.GITLAB_TOKEN,
        re.compile(_TOKEN_GUARD + r"glpat-[0-9A-Za-z_-]{20}"),
    ),
    (
        ValueSignature.SLACK_TOKEN,
        re.compile(_TOKEN_GUARD + r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    ),
    (
        ValueSignature.GOOGLE_API_KEY,
        re.compile(_TOKEN_GUARD + r"AIza[0-9A-Za-z_-]{35}"),
    ),
    (
        ValueSignature.STRIPE_KEY,
        re.compile(_TOKEN_GUARD + r"[sr]k_(?:live|test)_[0-9A-Za-z]{16,}"),
    ),
    (ValueSignature.TWILIO_KEY, re.compile(_TOKEN_GUARD + r"SK[0-9a-fA-F]{32}")),
    (
        ValueSignature.SENDGRID_KEY,
        re.compile(_TOKEN_GUARD + r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"),
    ),
    (ValueSignature.NPM_TOKEN, re.compile(_TOKEN_GUARD + r"npm_[A-Za-z0-9]{36}")),
    (
        ValueSignature.OPENAI_KEY,
        re.compile(_TOKEN_GUARD + r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    ),
    (
        ValueSignature.JWT,
        re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    ),
)
_EMBEDDED_CREDENTIAL_URL = re.compile(
    r"[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]+:([^/\s:@]+)@"
)
_BLOB_CHARS = re.compile(r"^[A-Za-z0-9+/_=-]+$")


class PropertyValueKind(StrEnum):
    """The shape of a property value, used to decide how to assess it."""

    EMPTY = "empty"
    PLACEHOLDER = "placeholder"
    ENCRYPTED = "encrypted"
    PATH_LIKE = "path_like"
    LITERAL = "literal"


class KeyNameTier(StrEnum):
    """Confidence tier of a property key (governs required value evidence)."""

    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class PropertyEntry:
    """A single parsed ``key = value`` pair.

    line_number is the 1-based physical line where the entry starts. The value
    is the logical value (continuations joined, escapes applied); it is never
    emitted to any output stream.
    """

    key: str
    value: str
    line_number: int


# --- Key-name matching --------------------------------------------------------

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_KEY_SEPARATORS = re.compile(r"[.\-_/\s]+")


def tokenize_key(key: str) -> tuple[str, ...]:
    """Split a property key into lowercased tokens.

    Splits on ``.`` ``_`` ``-`` ``/`` and whitespace, then on camelCase
    boundaries, so ``spring.datasource.password`` and ``dbPassword`` both yield a
    ``password`` token while ``compass`` yields only ``compass``.
    """

    tokens: list[str] = []
    for part in _KEY_SEPARATORS.split(key):
        if not part:
            continue
        for sub in _CAMEL_BOUNDARY.split(part):
            if sub:
                tokens.append(sub.lower())
    return tuple(tokens)


def _pattern_is_token_exact(pattern: str) -> bool:
    return len(pattern) <= 5 or pattern in _WEAK_TOKEN_PATTERNS


def _pattern_tier(pattern: str) -> KeyNameTier:
    if pattern in _WEAK_TOKEN_PATTERNS:
        return KeyNameTier.WEAK
    return KeyNameTier.STRONG


def classify_key_tier(key: str, patterns: tuple[str, ...]) -> KeyNameTier:
    """Classify a property key into a strength tier against the secret catalog.

    A pattern matches either as a whole token (short/ambiguous patterns) or as a
    substring within a token (long, low-collision patterns). A matched secret
    token immediately followed by a non-secret qualifier is demoted to WEAK. The
    strongest tier across all matches wins.
    """

    tokens = tokenize_key(key)
    best = KeyNameTier.NONE
    for raw_pattern in patterns:
        pattern = raw_pattern.lower()
        token_exact = _pattern_is_token_exact(pattern)
        for index, token in enumerate(tokens):
            matched = token == pattern if token_exact else pattern in token
            if not matched:
                continue
            tier = _pattern_tier(pattern)
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if following is not None and following in _QUALIFIER_DENYLIST:
                tier = KeyNameTier.WEAK
            if tier == KeyNameTier.STRONG:
                return KeyNameTier.STRONG
            best = KeyNameTier.WEAK
    return best


# --- Value signatures ---------------------------------------------------------


def match_value_signature(value: str) -> ValueSignature | None:
    """Return the high-confidence credential signature a value matches, if any.

    Detected independently of the key name (FR-003), so secrets hidden under
    benign key names are still reported.
    """

    candidate = value.strip()
    if not candidate:
        return None
    for signature, pattern in _SIGNATURE_PATTERNS:
        if pattern.search(candidate):
            return signature
    url_match = _EMBEDDED_CREDENTIAL_URL.search(candidate)
    if url_match is not None:
        password = url_match.group(1)
        if password and not any(ch in password for ch in "${}"):
            return ValueSignature.EMBEDDED_CREDENTIAL_URL
    if _looks_like_high_entropy_blob(candidate):
        return ValueSignature.HIGH_ENTROPY_BLOB
    return None


def _looks_like_high_entropy_blob(value: str) -> bool:
    if len(value) < BLOB_MIN_LENGTH or not _BLOB_CHARS.match(value):
        return False
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[+/_=-]")
    )
    if classes < 3:
        return False
    return _shannon_entropy(value) >= BLOB_MIN_ENTROPY


# --- Value classification & exclusions ----------------------------------------


def classify_value(value: str) -> PropertyValueKind:
    """Classify a property value to decide how it should be assessed.

    The EMPTY / PLACEHOLDER / ENCRYPTED branches are recognized so callers can
    short-circuit good-practice values before applying credential heuristics.
    """

    stripped = value.strip()
    if stripped == "":
        return PropertyValueKind.EMPTY
    if _is_placeholder(stripped):
        return PropertyValueKind.PLACEHOLDER
    if _is_encrypted(stripped):
        return PropertyValueKind.ENCRYPTED
    if _is_path_like(stripped):
        return PropertyValueKind.PATH_LIKE
    return PropertyValueKind.LITERAL


def is_sample_placeholder(value: str, extra_ignore: tuple[str, ...] = ()) -> bool:
    """Return whether a value is a documentation default / mask token.

    Conservative by design (research Decision 5): only tokens that are never a
    live secret are listed, so no real credential is suppressed.
    """

    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in _SAMPLE_VOCAB:
        return True
    if extra_ignore and lowered in {item.strip().lower() for item in extra_ignore}:
        return True
    return any(pattern.match(stripped) for pattern in _SAMPLE_PATTERNS)


def is_non_secret_shape(value: str, tier: KeyNameTier) -> bool:
    """Return whether a literal value has a recognized non-credential shape.

    Always-excluded shapes (every tier) are implausible as a live secret;
    kebab/snake identifiers are excluded only under WEAK keys so glued or
    hyphenated secrets under STRONG keys are never dropped (research Decision 6).
    """

    stripped = value.strip()
    if not stripped:
        return False
    if stripped.lower() in _ALG_ENUM:
        return True
    if _DOTTED_ID.match(stripped):
        return True
    if _is_bare_host(stripped):
        return True
    if _SEMVER.match(stripped):
        return True
    if _HEADER_NAME.match(stripped):
        return True
    if _DURATION.match(stripped):
        return True
    return tier == KeyNameTier.WEAK and _KEBAB_SNAKE.match(stripped) is not None


def _is_bare_host(value: str) -> bool:
    return (
        value.lower() == "localhost"
        or bool(_IPV4.match(value))
        or bool(_HOSTNAME_DOTTED.match(value))
    )


def placeholder_default(value: str) -> str | None:
    """Return the default segment of a defaulted placeholder, if present.

    Handles ``${VAR:-default}`` and ``${VAR:default}``; returns ``None`` when
    there is no default (or it is empty) so the caller treats it as a plain
    externalized reference.
    """

    match = re.match(r"^\$\{[^:}]+:-?(.*)\}$", value.strip())
    if match is None:
        return None
    default = match.group(1)
    return default if default != "" else None


def is_credential_like(value: str, tier: KeyNameTier) -> bool:
    """Return whether a literal value plausibly holds a credential for ``tier``.

    STRONG keys use the loose base gate (catches word-like human passwords);
    WEAK keys require random-secret-like length and entropy. Pure booleans and
    numbers never qualify.
    """

    if _is_boolean(value) or _is_number(value):
        return False
    length = len(value)
    if tier == KeyNameTier.STRONG:
        return length >= MIN_SECRET_LENGTH and _shannon_entropy(value) >= (
            MIN_ENTROPY_BITS_PER_CHAR
        )
    if tier == KeyNameTier.WEAK:
        return length >= MIN_WEAK_LENGTH and _shannon_entropy(value) >= MIN_WEAK_ENTROPY
    return False


def _is_placeholder(value: str) -> bool:
    if value.startswith("${") and value.endswith("}"):
        return True
    if value.startswith("#{") and value.endswith("}"):
        return True
    if value.startswith("@") and value.endswith("@") and len(value) > 1:
        return True
    if value.startswith("{{") and value.endswith("}}"):
        return True
    if value.startswith("$ENV{") and value.endswith("}"):
        return True
    if value.startswith("$(") and value.endswith(")"):
        return True
    if re.match(r"^%\(.+\)[sd]$", value):
        return True
    lowered = value.lower()
    return lowered.startswith(
        ("vault:", "awskms:", "aws-kms:", "sops:", "secret:", "secretref:", "env:")
    )


def _is_encrypted(value: str) -> bool:
    if value.startswith("ENC(") and value.endswith(")"):
        return True
    if value.startswith("{ENC(") and value.endswith(")}"):
        return True
    return value.startswith("{cipher}")


def _is_path_like(value: str) -> bool:
    if "/" in value or "\\" in value:
        return True
    lowered = value.lower()
    if any(lowered.endswith(suffix) for suffix in _KEY_FILE_SUFFIXES):
        return True
    return lowered.startswith("id_") and " " not in value


def _is_boolean(value: str) -> bool:
    return value.strip().lower() in {"true", "false", "yes", "no", "on", "off"}


def _is_number(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    try:
        float(candidate)
    except ValueError:
        return False
    return True


def _shannon_entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def parse_properties(text: str) -> tuple[PropertyEntry, ...]:
    """Parse ``.properties`` text into entries (common Java subset).

    Handles ``#``/``!`` comments, blank lines, ``=``/``:``/whitespace
    separators, backslash line continuations, and the escapes ``\\=`` ``\\:``
    ``\\t`` ``\\n`` ``\\r`` ``\\f`` ``\\\\``. Full ``\\uXXXX`` unescaping is out
    of scope.
    """

    entries: list[PropertyEntry] = []
    physical = text.splitlines()
    total = len(physical)
    index = 0
    while index < total:
        start_line = index + 1
        stripped = physical[index].lstrip()
        if stripped == "" or stripped[0] in ("#", "!"):
            index += 1
            continue

        logical = stripped
        while _ends_with_odd_backslashes(logical) and index + 1 < total:
            logical = logical[:-1] + physical[index + 1].lstrip()
            index += 1
        index += 1

        key, value = _split_key_value(logical)
        entries.append(PropertyEntry(key=key, value=value, line_number=start_line))
    return tuple(entries)


def _ends_with_odd_backslashes(line: str) -> bool:
    count = 0
    position = len(line) - 1
    while position >= 0 and line[position] == "\\":
        count += 1
        position -= 1
    return count % 2 == 1


def _split_key_value(line: str) -> tuple[str, str]:
    key_chars: list[str] = []
    index = 0
    separator_index: int | None = None
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line):
            nxt = line[index + 1]
            key_chars.append(_VALUE_ESCAPES.get(nxt, nxt))
            index += 2
            continue
        if char in _WHITESPACE or char in ("=", ":"):
            separator_index = index
            break
        key_chars.append(char)
        index += 1

    key = "".join(key_chars)
    if separator_index is None:
        return key, ""

    cursor = separator_index
    while cursor < len(line) and line[cursor] in _WHITESPACE:
        cursor += 1
    if cursor < len(line) and line[cursor] in ("=", ":"):
        cursor += 1
        while cursor < len(line) and line[cursor] in _WHITESPACE:
            cursor += 1

    return key, _unescape(line[cursor:])


def _unescape(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append(_VALUE_ESCAPES.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)
