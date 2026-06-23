# Contract: Precise `.properties` Secret Detection

Refines the 008 `properties-inspection` contract. Defines the observable behavior
of the layered, confidence-tiered classifier: the configuration surface, the
per-entry decision order, the tier and signature rules, the output format, and
the enforced accuracy. These are the behaviors acceptance and corpus tests assert
against. Carry-over behaviors from 008 (parsing, output `<path>#<key>`,
`files_scanned` dedup, scope/ignore rules, malformed/decode handling) are
unchanged unless stated.

## 1. Configuration contract (`[scan]` table)

- `property_name_patterns` — unchanged omit/empty/replace semantics, now matched
  **token-aware** (§3.2). User-supplied patterns are treated as STRONG tier.
- `property_value_ignore` *(new, optional)* — extra exact value tokens treated as
  benign (never flagged). Omit → packaged default (empty); `[]` → none; non-empty
  → replaces. Same rules as the ignore_* keys.
- Tier lists, qualifier denylist, sample vocabulary, signature catalog, shape
  predicates, and numeric thresholds are internal constants, not config.

## 2. Parsing contract

Unchanged from 008 (§2 of `008/contracts/properties-inspection.md`).

## 3. Per-entry decision order

For each `PropertyEntry`, evaluate in this exact order; the first finding wins,
the first stop ends evaluation.

### 3.1 Inline key material (unconditional — FR-010)

Value contains `-----BEGIN`: parse via `key_parsers`. `UNPROTECTED` → **finding**
(`origin=INLINE_KEY_MATERIAL`). `PUBLIC_ONLY` (incl. certificates),
`PROTECTED_WITH_PASSPHRASE`, `MALFORMED` → **stop** (not a finding). Key name
ignored.

### 3.2 Value signature (unconditional — FR-003)

Value matches a curated signature (AWS/GitHub/GitLab/Slack/Google/Stripe/Twilio/
SendGrid/npm/OpenAI token, JWT, embedded-credential URL `scheme://user:pw@` with a
non-placeholder `pw`, or a high-entropy base64/hex blob ≥ 32 chars, entropy ≥ 4.0,
≥ 3 char classes) → **finding** (`origin=VALUE_SIGNATURE`). Key name ignored.

### 3.3 Value kind (FR-008 / FR-009)

`classify_value(value)`:
- `EMPTY` → **stop**.
- `ENCRYPTED` (`ENC(…)`, `{ENC(…)}`, `{cipher}…`) → **stop**.
- `PLACEHOLDER` (`${…}`, `#{…}`, `@…@`, `{{…}}`, `$ENV{…}`, `$(…)`, `%(…)s`,
  `vault:`/`awskms:`/`sops:`/`secret:`/`secretref:`/`env:` schemes) → if a
  defaulted placeholder `${VAR:-default}` / `${VAR:default}` with a non-empty
  default, re-enter §3.2 and §3.5/§3.6 on the **default segment** at the key's
  tier (§3.4); else **stop**.

### 3.4 Key tier (FR-001 / FR-002)

`classify_key_tier(key, name_patterns)` → `STRONG` / `WEAK` / `NONE`.
- Tokenize the key (split on `. _ - /` whitespace + camelCase, lowercased).
- Substring-safe patterns match within a token; token-exact patterns match a
  whole token (§3.2 of research Decision 1).
- A matched secret token immediately followed by a qualifier-denylist token →
  demote to `WEAK`. Broad tokens (`key`/`token`/`private`) alone → `WEAK`.
- `NONE` → **stop** (signatures already handled in §3.2).

### 3.5 Path-like value (FR-007 of 008)

`PATH_LIKE` → resolve (relative → against the `.properties` directory),
canonicalize, follow only if it exists AND is within `scope.canonical_root_set`;
`UNPROTECTED` referenced file → **finding** (`origin=REFERENCED_KEY_FILE`).
Missing/out-of-scope → **stop**. Followed file reported to the caller for
`files_scanned` accounting (unchanged from 008).

### 3.6 Literal value exclusions and tiered gate (FR-004 / FR-005 / FR-006 / FR-007)

`LITERAL` value:
1. Sample / placeholder / mask vocabulary (or `property_value_ignore`) → **stop**.
2. Structured non-secret shape → **stop**. Always-excluded shapes (every tier):
   dotted/class identifier, algorithm/keystore/cipher constant, MIME type, HTTP
   header name, semantic version, bare host/IP/URL without embedded credential,
   public-key/cert marker. WEAK-only additional exclusions: generic kebab/snake
   identifier with all-word segments.
3. Tiered credential gate:
   - `STRONG` → `len >= 6` AND entropy `>= 2.5`, not bool/number → **finding**
     (`origin=PLAINTEXT_SECRET`).
   - `WEAK` → `len >= 12` AND entropy `>= 3.0` → **finding**
     (`origin=PLAINTEXT_SECRET`); otherwise **stop**.

## 4. Output contract (unchanged from 008 — FR-011, SC-004)

- One stdout line per offending property: `<canonical path>#<property key>`.
- Secret values never appear on stdout/stderr/logs. stderr summary reuses the
  `embedded-config-secret` usage category and MAY label the origin.

## 5. Accuracy contract (FR-014 / SC-001 / SC-002 / SC-006)

- Recall on the MUST-FLAG corpus partition == 100% (zero false negatives).
- False-positive rate on the MUST-NOT-FLAG partition ≤ 2% (0 on the curated
  core). The test fails the build when either threshold is breached.

## 6. Worked examples

| Property | Tier / path | Result |
| --- | --- | --- |
| `spring.datasource.password=hunter2xyz` | STRONG, literal | flag `PLAINTEXT_SECRET` |
| `admin.password=Summer2024` | STRONG, word-like | flag `PLAINTEXT_SECRET` |
| `db.password=changeme` | STRONG, sample vocab | **no finding** |
| `db.password=localhost` | STRONG, bare host shape | **no finding** |
| `datasource.url=jdbc:mysql://root:S3cr3t@db/app` | NONE key, signature | flag `VALUE_SIGNATURE` |
| `notify.webhook=xoxb-1234567890-abcdef` | NONE key, signature | flag `VALUE_SIGNATURE` |
| `routing.key=order.created.event` | WEAK, dotted id | **no finding** |
| `api.key=A1b2C3d4E5f6G7h8` | WEAK, len 16/H≈3.9 | flag `PLAINTEXT_SECRET` |
| `signing.key.alias=primary` | WEAK (demoted), word | **no finding** |
| `jwt.algorithm=RS256` | WEAK (demoted), enum | **no finding** |
| `cache.key.prefix=user:` | WEAK (demoted), len 5 | **no finding** |
| `password.min.length=8` | WEAK (demoted), number | **no finding** |
| `mail.password=${MAIL_PW}` | placeholder | **no finding** |
| `db.password=${DB_PW:-hunter2xyz}` | defaulted placeholder | flag `PLAINTEXT_SECRET` |
| `config.value=${PORT:-8080}` | defaulted placeholder, number | **no finding** |
| `jasypt.secret=ENC(b64==)` / `{cipher}AB…` | encrypted | **no finding** |
| `tls.cert=-----BEGIN CERTIFICATE-----…` | public material | **no finding** |
| `compass.center=12.5` / `tokenizer.mode=word` | NONE (token-aware) | **no finding** |
