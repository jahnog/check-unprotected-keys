"""Labeled `.properties` accuracy corpus (feature 009, FR-014).

Each case is ``(key, value, rationale)``. ``MUST_FLAG`` holds true unprotected
secrets that the scanner must report (zero false negatives); ``MUST_NOT_FLAG``
holds benign secret-named configuration that must not be reported (near-zero
false positives). Values are single physical lines (``\\n`` escapes are applied
by the parser) so the accuracy test can write ``key=value`` directly.

Inline-PEM and referenced-key-file recall are covered by the dedicated inspector
and integration tests (those require real key fixtures); this corpus exercises
the key-name / value / signature / shape / placeholder decision surface, where
the false-positive and false-negative risk concentrates.
"""

from __future__ import annotations

# The packaged default secret-name catalog (see the example TOML resource).
DEFAULT_PATTERNS: tuple[str, ...] = (
    "password",
    "passwd",
    "pwd",
    "pass",
    "secret",
    "private",
    "passphrase",
    "key",
    "token",
    "credential",
    "apikey",
)

_BLOB = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0"

MUST_FLAG: tuple[tuple[str, str, str], ...] = (
    # Strong-key plaintext credentials (incl. word-like human passwords).
    ("spring.datasource.password", "hunter2xyz", "strong key, random-ish literal"),
    ("admin.password", "Summer2024", "strong key, word-like human password"),
    ("db.passwd", "Tr0ub4dor", "strong key, mixed literal"),
    ("service.pwd", "S3cr3tValue", "strong key, mixed literal"),
    ("app.secret", "8f4b2c9e1a7d6", "strong key, hex-ish literal"),
    ("api.passphrase", "correct horse battery", "strong key, multiword passphrase"),
    # Weak/ambiguous key, random-secret-like literal.
    ("routing.key", "A1b2C3d4E5f6G7h8", "weak key, high-entropy literal"),
    ("api.token", "Z9y8X7w6V5u4T3s2R1q0", "weak key, high-entropy literal"),
    # Name-independent value signatures (key name not in the catalog).
    (
        "datasource.url",
        "jdbc:mysql://root:S3cr3t@db:3306/app",
        "embedded-credential URL",
    ),
    ("notification.webhook", "xoxb-1234567890-AbCdEfGhIjKl", "Slack token"),
    ("aws.access", "AKIAIOSFODNN7EXAMPLE", "AWS access key id"),
    ("gh.pat", "ghp_" + "a" * 36, "GitHub token"),
    (
        "session.jwt",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcDEF123456ghiJKL",
        "JWT",
    ),
    ("encryption.key", _BLOB, "weak key, high-entropy blob signature"),
    # Hardcoded placeholder default.
    ("db.password", "${DB_PW:-fallbackSecret9}", "hardcoded placeholder default"),
)

MUST_NOT_FLAG: tuple[tuple[str, str, str], ...] = (
    # Container words / non-secret keys (token-aware matching).
    ("compass.center", "12.5", "container word, not a key token"),
    ("tokenizer.mode", "word", "container word, not a key token"),
    ("monkey.patch.enabled", "true", "container word, boolean"),
    ("server.port", "8080", "non-secret key, number"),
    # Qualifier-demoted keys with benign values.
    ("signing.key.alias", "primary", "weak/demoted key, short word"),
    ("secret.rotation.days", "30", "weak/demoted key, number"),
    ("token.expiry.seconds", "3600", "weak/demoted key, number"),
    ("password.min.length", "8", "weak/demoted key, number"),
    ("api.key.header.name", "X-Api-Key", "weak/demoted key, header name"),
    ("cache.key.prefix", "user:", "weak/demoted key, short value"),
    ("oauth.token.algorithm", "HS256", "weak/demoted key, algorithm enum"),
    ("provider.secret.class", "com.example.SecretProvider", "weak/demoted, class id"),
    # Strong key, benign value shape / sample vocabulary.
    ("db.password", "changeme", "strong key, sample placeholder"),
    ("admin.password", "example", "strong key, sample placeholder"),
    ("db.password", "localhost", "strong key, bare hostname"),
    ("service.secret", "<your-secret>", "strong key, angle-bracket template"),
    ("keystore.type", "PKCS12", "non-secret key, keystore enum"),
    # Externalized references / encrypted wrappers.
    ("db.password", "${DB_PASSWORD}", "externalized reference"),
    ("api.secret", "ENC(QkVHRU5jcnlwdA==)", "jasypt-encrypted value"),
    ("jasypt.password", "{cipher}AAABBBCCCDDD", "spring cloud config cipher"),
    ("vault.key", "vault:secret/data/app#key", "vault reference scheme"),
    ("tpl.password", "{{ db_password }}", "templated reference"),
    # URLs/hosts without embedded credentials.
    ("oauth.token.uri", "https://auth.example.com/token", "bare URL, no credential"),
    ("redis.url", "redis://cache.internal:6379", "bare URL, no credential"),
    # Public material.
    (
        "tls.cert",
        "-----BEGIN CERTIFICATE-----\\nMIIBexample\\n-----END CERTIFICATE-----",
        "certificate (public) material",
    ),
)
