# Quickstart: Validating Precise `.properties` Secret Detection

End-to-end validation that detection reports real secrets (zero false negatives)
and stays quiet on benign secret-named configuration (near-zero false positives).
References: [spec.md](spec.md), [contracts/properties-detection.md](contracts/properties-detection.md),
[data-model.md](data-model.md).

## Prerequisites

- Python 3.12, project installed in editable mode (`uv sync` / `pip install -e .`).
- Console entry point: `check-unprotected-keys` (`check_unprotected_keys.cli:main`).

## Scenario A — Benign secret-named config is silent (US1, SC-002)

1. Create a workspace `app/application.properties` containing only benign
   secret-named entries:
   - `signing.key.alias=primary`, `jwt.algorithm=RS256`,
     `cache.key.prefix=user:`, `oauth.token.uri=https://auth.example.com/token`,
     `password.min.length=8`, `keystore.type=PKCS12`,
     `key.serializer=org.apache.kafka.common.serialization.StringSerializer`,
     `db.password=changeme`, `db.host=localhost`,
     `compass.center=12.5`, `tokenizer.mode=word`.
2. Run a default scan rooted at `app/`.
3. **Expected**: exit code 0, **no** findings on stdout. (Every line is excluded
   by token-aware matching, qualifier demotion, shape/sample exclusions, or the
   tier gate — see the contract worked-examples table.)

## Scenario B — Real secrets are reported, including under benign keys (US2, SC-001/SC-005)

1. In the same workspace add `secrets/secrets.properties`:
   - `spring.datasource.password=hunter2xyz` (STRONG literal),
   - `admin.password=Summer2024` (word-like human password),
   - `datasource.url=jdbc:mysql://root:S3cr3t@db:3306/app` (NONE key, embedded-credential URL),
   - `notify.webhook=xoxb-1234567890-AbCdEfGhIjK` (NONE key, Slack token signature),
   - `api.key=A1b2C3d4E5f6G7h8` (WEAK key, high-entropy literal),
   - `db.password=${DB_PW:-fallbackSecret9}` (hardcoded placeholder default),
   - `ssl.key.file=keys/server.key` pointing to an unprotected PEM in scope,
   - `note=-----BEGIN RSA PRIVATE KEY-----\n…` inline unprotected key.
2. Run a default scan.
3. **Expected**: exit code 1; one stdout line per offending property in
   `<path>#<key>` form (e.g. `…/secrets.properties#datasource.url`); the followed
   `keys/server.key` reported once; **no secret value** anywhere in stdout/stderr.

## Scenario C — Good-practice externalization/encryption is silent (US4)

1. Add `config/secure.properties`:
   - `db.password=${DB_PASSWORD}`, `api.secret=ENC(QkVH==)`,
     `jasypt.token={cipher}AAABBBCCC`, `vault.key=vault:secret/data/app#key`,
     `tpl.password={{ db_password }}`, `tls.cert=-----BEGIN CERTIFICATE-----…`.
2. Run a default scan.
3. **Expected**: no findings — all recognized as references, encrypted wrappers,
   or public material.

## Scenario D — Enforced accuracy thresholds (US5, SC-006)

1. Run the labeled-corpus accuracy test:
   `pytest tests/unit/test_properties_accuracy.py -q`.
2. **Expected**: passes — recall == 100% on MUST-FLAG, false-positive rate ≤ 2%
   (0 on the curated core) on MUST-NOT-FLAG. Reintroducing a false positive or
   false negative makes this test fail.

## Full quality gate (Constitution III / IV, NFR-002/003)

```
pytest                              # unit + integration + accuracy, cov-fail-under=85
ruff check src/ tests/
ruff format --check src/ tests/
pyright src/
check-unprotected-keys --print-example-config   # smoke the updated bundled config
```

**Done when**: Scenarios A–D behave as described and all quality-gate commands
pass. Triage any failing pre-existing test (test logic vs. implementation) and
record the conclusion before changing it.
