"""Static detection catalogs and thresholds for ``.properties`` heuristics.

Pure reference data (spec 010 FR-010): no logic lives here. Locale-related
tables are in :mod:`.locales`.
"""

from __future__ import annotations

import re

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
KEY_FILE_SUFFIXES = (".pem", ".key", ".ppk", ".p8", ".pk8", ".ovpn", ".tfvars")

# --- Key-name matching catalogs (research Decisions 1-2) ----------------------
#
# STRONG_* catalogs document the recommended default pattern set. Runtime
# classification uses config-supplied ``property_name_patterns`` (plus
# WEAK_TOKEN_PATTERNS for tier demotion); these STRONG sets are not wired into
# ``classify_key_tier`` so operator config remains authoritative.

# Long, low-collision patterns matched as a substring of a single key token.
STRONG_SUBSTRING_PATTERNS = frozenset(
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
WEAK_TOKEN_PATTERNS = frozenset({"key", "keys", "token", "tokens", "private", "priv"})
# Tokens that mark the key as STRONG when matched whole.
STRONG_TOKEN_PATTERNS = frozenset({"pass", "pwd"})

# When the token immediately after a matched secret token is one of these, the
# key denotes metadata *about* a secret, not the secret itself -> demote to WEAK.
QUALIFIER_DENYLIST = frozenset(
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
SAMPLE_VOCAB = frozenset(
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
SAMPLE_PATTERNS = (
    re.compile(r"^[xX]{4,}$"),
    re.compile(r"^\*{4,}$"),
    re.compile(r"^•{3,}$"),
    re.compile(r"^<[^>]+>$"),
    re.compile(r"^\[[^\]]+\]$"),
    re.compile(r"^\.{3,}$"),
)

# Algorithm / keystore / format constants (case-insensitive exact match).
ALG_ENUM = frozenset(
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

DOTTED_ID = re.compile(r"^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)+$")
SEMVER = re.compile(r"^v?\d+\.\d+(\.\d+)?([-+][0-9A-Za-z.-]+)?$")
HEADER_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*(-[A-Z][A-Za-z0-9]*)+$")
KEBAB_SNAKE = re.compile(r"^[A-Za-z][A-Za-z0-9]*([._\-][A-Za-z0-9]+)+$")
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
HOSTNAME_DOTTED = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}))+$"
)
DURATION = re.compile(
    r"^\d+(\.\d+)?\s?"
    r"(ms|s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|"
    r"hours|d|day|days|w|week|weeks|kb|mb|gb|tb|b)$",
    re.IGNORECASE,
)
