# Feature Specification: Precise `.properties` Secret Detection (Near-Zero False Positives, Zero False Negatives)

**Feature Branch**: `feature/properties-detection-accuracy`

**Created**: 2026-06-23

**Status**: Draft

**Input**: User description: "analyze the unencrypted keys and passwords detection in the .properties files. it is showing a great number of false positives. think step by step to find a way to do the detection with almost no false positives. but the priority is to avoid all false negatives."

## Context

Feature 008 added `.properties` content inspection. In practice it reports a large
number of false positives. Two root causes drive the noise:

1. **Substring key-name matching** — a secret-name pattern matches anywhere in the
   key, so `pass` matches `compass`/`bypass`, `key` matches `routing.key`,
   `cache.key.prefix`, `key.serializer`, `token` matches `tokenizer`, and `secret`
   matches `secret.rotation.days`. Many non-credential properties pass the name gate.
2. **A single, deliberately loose value gate** — a literal value is treated as a
   plaintext secret when it is `len >= 6` AND Shannon entropy `>= 2.5` and not a
   pure boolean/number. This flags ordinary configuration values: hostnames
   (`localhost`), class/package identifiers, algorithm and keystore constants
   (`RS256`, `PKCS12`), sample placeholders (`changeme`), header names, and more.

At the same time, the current design can MISS real secrets: a credential under a
key whose name is not in the catalog (for example a JDBC URL with an embedded
password, or an inline cloud token) is never flagged, because detection is gated
on the key name.

This feature replaces the single loose gate with a **layered, confidence-tiered
classifier** that raises precision sharply while preserving — and in places
improving — recall. The guiding priority is explicit: **avoid all false negatives
on plausible secrets; reduce false positives to near zero.**

## Clarifications

### Session 2026-06-23

- Q: For weak/ambiguous key names (substring `key`, or qualified keys like
  `signing.key.alias`, `cache.key.prefix`), how should the value be judged? → A:
  **Tiered evidence** — strong, unambiguous credential key names keep the lenient
  gate so even word-like human passwords are caught; weak/ambiguous key names
  require stronger value evidence (high entropy/length or a known secret
  signature). A genuine high-entropy secret under an odd key is still caught.
- Q: Should detection add an unconditional value-signature layer (provider tokens,
  JWTs, PEM private keys, base64/hex high-entropy blobs, connection strings with
  embedded credentials) that fires regardless of key name? → A: **Yes** — it gives
  a high-confidence, name-independent basis that simultaneously reduces false
  positives (clear yes/no on known formats) and reduces false negatives (catches
  secrets hidden under benign key names). This is what makes "no false negatives"
  achievable.
- Q: How should the "almost no false positives / zero false negatives" claim be
  measured and kept true? → A: **Labeled corpus + thresholds** — build a labeled
  `.properties` corpus (MUST-FLAG true secrets + MUST-NOT-FLAG benign secret-named
  config) and assert measurable precision/recall gates in the test suite so
  regressions fail the build.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Benign Secret-Named Configuration Is No Longer Reported (Priority: P1)

As a security operator running scans across real codebases, I want ordinary
configuration values that merely sit under secret-sounding keys to stop being
reported, so that the findings list is small, trustworthy, and worth acting on.

**Why this priority**: The false-positive flood is the reported problem. A
scanner that drowns the operator in noise is abandoned. This is the core value of
the feature.

**Independent Test**: Run a default scan over a `.properties` file populated only
with benign-but-secret-named entries (for example `key.serializer=...`,
`signing.key.alias=primary`, `jwt.algorithm=RS256`, `cache.key.prefix=user:`,
`oauth.token.uri=https://auth.example.com/token`, `db.password=changeme`,
`keystore.type=PKCS12`, `provider.class=com.example.KeyProvider`) and confirm
**zero** findings are produced.

**Acceptance Scenarios**:

1. **Given** a property whose key only contains a secret word as part of a larger
   word (for example `compass.center`, `tokenizer.mode`, `monkey.patch.enabled`),
   **When** a scan runs, **Then** it is not reported (the secret word is not a
   key token).
2. **Given** a property whose matched secret token is qualified by a non-secret
   descriptor (for example `signing.key.alias`, `api.key.header.name`,
   `secret.rotation.days`, `token.expiry.seconds`, `password.min.length`),
   **When** a scan runs, **Then** it is not reported unless its value carries
   independent secret evidence.
3. **Given** a secret-named property whose value is a recognizable non-secret
   shape (class/package identifier, algorithm/keystore constant, bare
   hostname/URL without embedded credentials, duration/size literal, header name,
   MIME type, semantic version), **When** a scan runs, **Then** it is not reported.
4. **Given** a secret-named property whose value is a recognized sample,
   placeholder, or mask token (for example `changeme`, `your_password_here`,
   `example`, `redacted`, `none`, `n/a`, `xxxxxxxx`, `********`, `<password>`),
   **When** a scan runs, **Then** it is not reported.

---

### User Story 2 - Real Secrets Are Never Missed (Priority: P1)

As a security operator, I want every plausible unprotected secret to be reported
even when it hides under an unconventional key name or an unusual format, so that
tightening precision never lets a real credential through.

**Why this priority**: The user's explicit non-negotiable is "avoid all false
negatives." Precision gains are only acceptable if recall on real secrets is
preserved or improved.

**Independent Test**: Run a default scan over a `.properties` file whose entries
include real secrets across varied key names and forms — a high-entropy password
under `db.password`, a word-like human password under `admin.password`, an AWS
key id/secret pair, a GitHub token, a JWT, an inline PEM **private** key, and a
JDBC/Mongo URL with an embedded password under a non-secret key name — and
confirm **all** of them are reported.

**Acceptance Scenarios**:

1. **Given** a value that matches a known credential signature (cloud-provider
   token, API key, JWT, PEM/OpenSSH/PuTTY private key, or a connection/URI string
   with embedded `user:password@`), **When** a scan runs, **Then** it is reported
   regardless of the key name.
2. **Given** a strong-named secret property whose value is a word-like human
   password (for example `admin.password=Summer2024`), **When** a scan runs,
   **Then** it is reported.
3. **Given** a credential placed under a key whose name is NOT in the secret-name
   catalog (for example `datasource.url=jdbc:mysql://root:S3cr3t@db:3306/app`),
   **When** a scan runs, **Then** it is reported on value-signature grounds.
4. **Given** a defaulted externalized placeholder whose default segment is itself
   a hardcoded credential (for example `db.password=${DB_PASSWORD:-hunter2xyz}`),
   **When** a scan runs, **Then** the default segment is assessed and the property
   is reported.

---

### User Story 3 - Confidence Is Tiered by Key-Name Strength (Priority: P2)

As an operator, I want the strength of a key name to govern how much value
evidence is required, so that obviously-credential keys catch even weak passwords
while broad/ambiguous keys do not fire on ordinary config.

**Why this priority**: The tiered rule is the mechanism that lets US1 and US2
coexist. It is secondary to the outcomes but is the testable engine behind them.

**Independent Test**: Place the same medium-strength value under a STRONG key
(`account.password`) and under a WEAK/ambiguous key (`routing.key`); confirm the
STRONG key reports it and the WEAK key does not, while a clearly high-entropy or
signature-matching value is reported under both.

**Acceptance Scenarios**:

1. **Given** a STRONG, unambiguous credential key (for example `password`,
   `passwd`, `pwd`, `secret`, `credential`, `passphrase`, `apikey`,
   `private.key`), **When** its value clears the base credential gate or is a
   word-like password (and is not a sample/placeholder), **Then** it is reported.
2. **Given** a WEAK/ambiguous key (broad token such as `key`/`token`/`pass`/
   `private` alone, or any qualifier-demoted key), **When** its value is only
   medium-strength and matches no signature, **Then** it is not reported.
3. **Given** a WEAK/ambiguous key whose value is high-entropy/sufficient-length
   (consistent with a random secret) or matches a value signature, **When** a
   scan runs, **Then** it is reported.

---

### User Story 4 - Good-Practice Externalization and Encryption Are Recognized (Priority: P2)

As an operator who externalizes or encrypts secrets, I want the broad range of
real-world reference and encryption forms to be recognized as non-findings, so
that correctly-secured configuration never appears in results.

**Why this priority**: Externalized/encrypted values are a large share of
secret-named entries in real configs; recognizing more of them removes a whole
class of false positives.

**Independent Test**: Run a scan over a `.properties` file whose secret-named
values use varied externalization/encryption forms (Spring `{cipher}…`, Jasypt
`ENC(…)`/brace form, defaulted `${VAR:-…}` with a non-secret default, double-brace
`{{…}}`, and reference schemes such as `vault:`, `awskms:`, `sops:`, `env:`) and
confirm none are reported.

**Acceptance Scenarios**:

1. **Given** a value wrapped in a recognized encryption form (`ENC(…)`,
   `{cipher}…`, brace-wrapped `ENC`), **When** a scan runs, **Then** it is not
   reported.
2. **Given** a value that is an externalized reference (`${…}`, `@…@`, `#{…}`,
   `{{…}}`, `vault:`/`awskms:`/`sops:`/`env:`/`secret:` scheme), **When** a scan
   runs, **Then** it is not reported.
3. **Given** a defaulted placeholder whose default is a non-secret
   (`${PORT:-8080}`), **When** a scan runs, **Then** it is not reported; the
   credential-bearing-default case is covered by US2 scenario 4.

---

### User Story 5 - Accuracy Is Measured and Enforced (Priority: P2)

As a maintainer, I want the "near-zero false positives, zero false negatives"
claim backed by a labeled corpus and automatic thresholds, so that future changes
cannot silently regress detection quality.

**Why this priority**: Without measurement the accuracy claim is unverifiable and
fragile. It does not change runtime behavior, so it is secondary to the detection
work, but it is what makes the guarantee durable.

**Independent Test**: Inspect the test suite and confirm it contains a labeled
`.properties` corpus partitioned into MUST-FLAG and MUST-NOT-FLAG cases, and that
the suite fails when recall on MUST-FLAG drops below 100% or the false-positive
rate on MUST-NOT-FLAG exceeds the configured target.

**Acceptance Scenarios**:

1. **Given** the labeled corpus, **When** the suite runs, **Then** 100% of
   MUST-FLAG cases are reported and the MUST-NOT-FLAG false-positive rate is at or
   below target.
2. **Given** a change that reintroduces a false positive or a false negative,
   **When** the suite runs, **Then** it fails on the corresponding threshold.

---

### Edge Cases

- **Key tokenization**: keys are split into tokens on `.`, `_`, `-`, `/`, and
  camelCase boundaries; a secret word matches only as a whole token (so `password`
  matches `spring.datasource.password` and `dbPassword`, but `pass` does not match
  `compass`).
- **Qualifier demotion**: a secret token immediately qualified by a non-secret
  descriptor (`.alias`, `.id`, `.name`, `.type`, `.algorithm`, `.store`,
  `.store.type`, `.provider`, `.header`, `.prefix`, `.suffix`, `.enabled`,
  `.disabled`, `.required`, `.length`, `.size`, `.count`, `.ttl`, `.timeout`,
  `.interval`, `.expiry`, `.rotation`, `.policy`, `.format`, `.encoding`,
  `.class`, `.strategy`, `.location`, `.pattern`, `.regex`, `.serializer`,
  `.deserializer`, `.url`, `.uri`, `.endpoint`, `.version`) is treated as
  weak/ambiguous, not strong.
- **Public key material**: inline `-----BEGIN PUBLIC KEY-----` and
  `-----BEGIN CERTIFICATE-----` blocks, and `*.public.*` / `public.key` entries,
  are public by design and MUST NOT be reported. Only PRIVATE/unprotected key
  material is a finding.
- **Sample/placeholder/mask vocabulary**: documentation defaults and masked values
  (`changeme`, `change_me`, `your_password`, `password`, `secret`, `example`,
  `dummy`, `test`, `placeholder`, `tbd`, `redacted`, `none`, `null`, `n/a`,
  repeated `x`/`*` runs, angle-bracket templates `<...>`) are not live secrets and
  MUST NOT be reported.
- **Value signatures under any key name**: provider tokens, JWTs, private-key
  blocks, base64/hex high-entropy blobs of sufficient length, and connection/URI
  strings with embedded `user:password@` are reported regardless of key name.
- **Connection strings**: a URL/URI with an embedded credential is a finding; a
  bare URL/URI without an embedded credential (for example `oauth.token.uri=…`) is
  not.
- **Defaulted placeholders**: `${VAR:-default}` / `${VAR:default}` is a non-finding
  unless the default segment is itself credential-like, in which case it is
  assessed and may be reported.
- **Word-like human passwords**: under a STRONG key, low-entropy but credential-
  shaped values (for example `Summer2024`) are still reported (recall priority);
  the sample/placeholder vocabulary is the only word-like exclusion.
- **Carry-over behaviors (unchanged from 008)**: comment/blank-line skipping,
  `=`/`:`/whitespace separators, line continuations, escapes, case-insensitive
  matching, key-file reference following with `.properties`-relative resolution
  and scope enforcement, `files_scanned` dedup, ignore rules, malformed/unreadable
  reporting, and UTF-8→Latin-1 decode fallback.
- **Duplicate keys**: each occurrence is assessed; the file is reported if any
  qualifying occurrence is found.
- **Message/i18n bundles**: a `.properties` file recognized as a message bundle
  (locale-suffixed like `messages_es.properties`, or a known bundle base name)
  has its name-gated credential detection skipped; only inline key material and
  recognized value signatures are reported. A non-bundle config file whose name
  merely collides with a short locale code (for example `service_id.properties`)
  is still fully scanned.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST match secret-name patterns against **whole key tokens**
  (key split on `.`, `_`, `-`, `/`, and camelCase boundaries), not as arbitrary
  substrings, so that words that merely contain a secret pattern (for example
  `compass`, `bypass`, `monkey`, `tokenizer`, `keyboard`) are not matched.
- **FR-002**: System MUST classify each secret-named key into a confidence tier:
  **STRONG** (unambiguous credential names — at minimum `password`, `passwd`,
  `pwd`, `secret`, `credential`, `passphrase`, `apikey`, and private-key forms
  such as `private.key`/`privatekey`), **WEAK/AMBIGUOUS** (broad tokens such as
  `key`, `token`, `pass`, `private` used alone, or any key whose secret token is
  qualified by a recognized non-secret descriptor), or **NONE** (no secret token).
- **FR-003**: System MUST report a value as a secret — **independently of the key
  name** — when the value matches a recognized high-confidence credential
  signature, including at minimum: cloud-provider and service token formats (for
  example AWS access key id and secret access key, GitHub/GitLab tokens, Slack
  tokens, Google API keys, Stripe keys), JSON Web Tokens, PEM/OpenSSH/PuTTY
  **private** key material, and connection/URI strings carrying an embedded
  credential (`scheme://user:password@host`). The exact signature catalog is
  finalized in planning and MUST be curated for near-zero false positives.
- **FR-004**: For a **STRONG** key with a literal value, System MUST report the
  value when it clears the base credential gate (a minimum length AND minimum
  entropy/character-diversity threshold) OR is a word-like human-password shape,
  except when the value is in the sample/placeholder/mask vocabulary (FR-006) or
  is unambiguously non-secret material (class/package identifier, pure
  algorithm/keystore constant, bare hostname/URL without embedded credentials).
- **FR-005**: For a **WEAK/AMBIGUOUS** key with a literal value, System MUST report
  the value only when it clears a **stricter** bar consistent with random secret
  material (higher length/entropy than the STRONG-tier base gate) OR matches a
  value signature (FR-003). Medium-strength, word-like, or structured values under
  weak/ambiguous keys MUST NOT be reported.
- **FR-006**: System MUST NOT report a literal value that is a recognized sample,
  placeholder, documentation default, or mask token (for example `changeme`,
  `change_me`, `your_password_here`, `example`, `dummy`, `placeholder`, `redacted`,
  `none`, `null`, `n/a`, `tbd`, runs of `x` or `*`, angle-bracket templates
  `<...>`). This exclusion applies in every tier and MUST be conservative enough to
  carry near-zero false-negative risk.
- **FR-007**: System MUST NOT report a literal value whose shape is a recognized
  non-credential form when the key is WEAK/AMBIGUOUS: dotted/package or class
  identifier, enumerated algorithm/keystore/format constant, MIME type, HTTP
  header name, bare hostname or URL without embedded credentials, semantic version,
  or duration/size literal. Under a STRONG key, such a value is excluded only when
  it also fails the base credential gate (FR-004), so plausible secrets under
  strong keys are never dropped.
- **FR-008**: System MUST recognize an expanded set of externalized-reference and
  encrypted-value forms as non-findings, including at minimum: `${…}`, `@…@`,
  `#{…}`, double-brace `{{…}}`, defaulted placeholders `${VAR:-default}` /
  `${VAR:default}`, reference schemes (`vault:`, `vault://`, `awskms:`, `sops:`,
  `env:`, `secret:`), and encryption wrappers `ENC(…)`, brace-wrapped `ENC`, and
  Spring Cloud Config `{cipher}…`.
- **FR-009**: For a defaulted placeholder, System MUST assess the **default
  segment** for credential-likeness and value signatures; the property is reported
  only when that default segment is itself an unprotected secret (FR-003/FR-004),
  and is otherwise a non-finding.
- **FR-010**: System MUST treat inline **public** key material and certificates
  (`-----BEGIN PUBLIC KEY-----`, `-----BEGIN CERTIFICATE-----`) and `public.key`/
  `*.public.*` entries as non-secrets; only inline PRIVATE/unprotected key material
  is reported.
- **FR-011**: System MUST NOT emit any property value to any output stream;
  findings identify the file path and the offending property key/location only,
  preserving the existing `<file path>#<property key>` output form. The stderr
  summary MAY additionally label each finding's origin/confidence (for example
  plaintext-secret, value-signature, inline-key-material, referenced-key-file)
  without exposing the value.
- **FR-012**: System MUST preserve all carry-over behaviors from the existing
  `.properties` inspection: token/separator parsing, line continuations, escapes,
  case-insensitive matching, key-file reference following with
  `.properties`-relative resolution and authorized-scope enforcement,
  `files_scanned` dedup, ignore-rule honoring, malformed/unreadable-file
  reporting, and decode fallback.
- **FR-013**: The secret-name catalog and the new classification inputs (at
  minimum the secret-name catalog and an exclusion/override surface for
  organization-specific needs) MUST be configurable with the project's existing
  omit/empty/replace semantics; shipped defaults MUST produce the precision/recall
  outcomes with no configuration. Numeric thresholds MAY remain internal constants.
- **FR-014**: The test suite MUST include a labeled `.properties` accuracy corpus
  partitioned into **MUST-FLAG** (true unprotected secrets spanning varied key
  names, value forms, and the value-signature catalog) and **MUST-NOT-FLAG**
  (benign secret-named configuration spanning the false-positive classes above),
  and MUST assert: recall = 100% on MUST-FLAG and false-positive rate at or below
  the configured target on MUST-NOT-FLAG, failing the build on regression.
- **FR-015**: System MUST recognize i18n / message resource-bundle `.properties`
  files by filename (a Java ResourceBundle locale suffix such as `_es` / `_en_US`,
  or a known message-bundle base name such as `messages` / `labels` /
  `ApplicationResources`) and, for those files, MUST NOT apply the name-gated
  plaintext-credential gate or key-file reference following — their values are
  natural-language text *about* secrets, not secrets. The unconditional
  inline-key-material (FR-010) and value-signature (FR-003) layers MUST still
  apply, so a genuinely embedded secret in such a file is never missed.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and infrastructure concerns,
  and MUST comply with SOLID, Clean Code, DRY, and KISS. The layered classifier
  (tokenization, tiering, value signatures, value-shape exclusions, expanded
  externalization recognition) MUST live in the existing pure properties domain
  module, reusing the established key-material assessment rather than duplicating
  parsing.
- **NFR-002**: Feature MUST describe required unit tests that validate the
  change, any needed integration or contract tests, and the expected
  coverage-report impact; after implementation the full unit-test suite and
  coverage report are run, with any failing test triaged (test logic vs.
  implementation logic) before the test or code is changed.
- **NFR-003**: Feature MUST remain compliant with the project's linting,
  formatting, and static analysis gates.
- **NFR-004**: Feature MUST state whether standalone packaging, entry points,
  release artifacts, or deployment documentation change. (Expected: bundled
  example configuration and README update for the refined behavior; no new runtime
  dependency; entry points unchanged.)

### Key Entities *(include if feature involves data)*

- **Property Entry**: a parsed key/value pair with source location; the unit of
  name matching and value assessment (carried over from 008).
- **Key Token Set**: the tokens extracted from a property key, against which
  secret-name matching and qualifier demotion operate.
- **Key-Name Strength Tier**: STRONG / WEAK-AMBIGUOUS / NONE, derived from token
  matching and the qualifier denylist; governs how much value evidence is required.
- **Secret-Name Catalog & Qualifier Denylist**: the configurable patterns marking
  secret keys and the recognized non-secret descriptors that demote them.
- **Value Classification**: EMPTY / externalized-reference / encrypted /
  path-like / sample-placeholder / non-secret-shape / signature-match / literal —
  the determination applied to a value.
- **Value Signature Catalog**: the curated set of high-confidence credential
  formats detected independently of key name.
- **Sample/Placeholder Vocabulary**: the curated set of documentation defaults and
  mask tokens that are never reported.
- **Labeled Accuracy Corpus**: the MUST-FLAG / MUST-NOT-FLAG partitions and their
  enforced precision/recall thresholds.
- **Finding**: a reported exposure tying a properties file and offending property
  location (and an origin/confidence label) to an unprotected secret, never the
  secret value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the MUST-FLAG partition of the labeled corpus, 100% of true
  unprotected secrets are reported in a default scan (zero false negatives).
- **SC-002**: On the MUST-NOT-FLAG partition (benign secret-named configuration),
  the false-positive rate is at most 2%, and 0 on the curated core set.
- **SC-003**: Against a representative real-world sample of `.properties` files,
  false positives are reduced by at least 90% relative to the current behavior,
  with no reduction in true-positive detection.
- **SC-004**: Across all scan output streams, the secret value string for a
  reported property appears 0 times, while the file path and property key appear
  for every finding.
- **SC-005**: 100% of credentials expressed in a recognized signature form
  (provider tokens, JWTs, private-key blocks, credential-bearing connection
  strings) are reported even when placed under a key name that is not in the
  secret-name catalog.
- **SC-006**: The accuracy thresholds (SC-001 recall and SC-002 false-positive
  rate) are enforced automatically by the test suite, which fails when either is
  breached.
- **SC-007**: An operator can adjust the secret-name catalog and exclusion surface
  entirely through configuration, with no code changes, and the shipped defaults
  achieve SC-001–SC-003 with no configuration.

## Assumptions

- **Builds on 008**: This feature refines the detection decision logic of the
  existing `.properties` inspection. Parsing, output format, `files_scanned`
  accounting, scope/ignore rules, reference following, and malformed-file handling
  are reused unchanged unless a requirement above states otherwise.
- **Format scope**: Java-style `.properties` files only; other formats (YAML, XML,
  `.ini`, `.cfg`) remain out of scope. `.env` files keep their existing handling.
- **Tiering**: The STRONG vs WEAK/AMBIGUOUS classification and the qualifier
  denylist are shipped as curated defaults; the exact membership lists are
  finalized in planning and validated against the corpus.
- **Value signatures**: The signature catalog is a conservative, well-known set
  chosen for near-zero false positives; exact patterns are finalized in planning.
  A high-entropy base64/hex blob is treated as a signature only above a length
  threshold sufficient to exclude ordinary identifiers.
- **Thresholds**: The base credential gate (STRONG tier) and the stricter gate
  (WEAK tier) are internal numeric constants finalized in planning and tuned
  against the labeled corpus; the combined length-and-entropy shape is fixed by
  this spec.
- **Exclusion vocabularies**: The sample/placeholder/mask vocabulary and the
  non-secret value-shape rules are conservative and corpus-validated so that no
  MUST-FLAG case is suppressed.
- **Defaulted placeholders**: A hardcoded credential supplied as a placeholder
  default is still a real exposure and is therefore assessed (FR-009).
- **Public material**: Public keys and certificates are intentionally not reported;
  the existing key-material classification distinguishes private from public.
- **No new dependency**: Detection uses standard text/pattern processing and the
  existing key-material assessment; no new runtime dependency is introduced.
- **Reduction baseline (SC-003)**: "Current behavior" is the detection shipped by
  feature 008; the representative sample and the 90% reduction are measured with
  the same input set before and after.
- **Message bundles (FR-015)**: i18n resource bundles are identified by filename
  (a ResourceBundle locale suffix with a valid ISO 639-1 language — excluding a
  few collision-prone codes for arbitrary base names — or a known bundle base
  name). They are assumed to contain no live secrets; the inline-key-material and
  value-signature layers remain the safety net against that assumption being
  wrong.
