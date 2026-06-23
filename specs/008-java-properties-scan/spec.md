# Feature Specification: Scan Java `.properties` Files for Unprotected Secrets

**Feature Branch**: `008-java-properties-scan`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "add the java .properties files to the files to be checked, and check if the have a property called password, pass, private, etc, that can store a password or a key file without encryption."

## Clarifications

### Session 2026-06-22

- Q: What qualifies a secret-named property's value as an unprotected plaintext secret worth reporting? → A: **Name + value heuristics** — flag only when the key matches a secret-name pattern AND the value also looks credential-like (sufficient length/entropy, or inline key material), excluding obvious non-secrets such as small integers and booleans, in addition to the always-excluded empty/placeholder/encrypted values.
- Q: When a secret-named property's value is a filesystem path to a key file, what should the scanner do? → A: **Follow and assess** — resolve the referenced path and assess that key file's protection using the existing key-material classification, reporting it when unprotected.
- Q: How should findings be emitted when one `.properties` file contains multiple secret properties? → A: **One stdout line per offending property**, using a `<file path>#<property key>` form so each finding is independently greppable from stdout; per-property detail also appears in the stderr summary.
- Q: When a followed key-file reference uses a relative path, what base resolves it? → A: **The properties file's own directory** (matching common Java/Spring config-relative resource semantics).
- Q: What concrete floor anchors the credential-likeness heuristic for plaintext values? → A: **Combined length and entropy** — a value is flagged only when it meets both a minimum length and a minimum entropy/character-diversity threshold (exact bounds finalized in planning); pure booleans and integers never qualify.
- Q: How does a followed key-file reference affect `files_scanned`? → A: **Count once, deduplicated** — a referenced key file counts toward `files_scanned` exactly once and is deduplicated against the same file when also discovered directly by the walk.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect Plaintext Secrets in Properties Files by Default (Priority: P1)

As a security operator scanning a codebase, I want a default scan to read Java
`.properties` configuration files and flag any property whose name signals it
holds a credential (for example `password`, `pass`, `private`, `secret`) when
its value is an unprotected plaintext secret, so that hard-coded credentials in
configuration are surfaced without my having to grep for them manually.

**Why this priority**: Hard-coded credentials in `.properties` files are one of
the most common real-world secret exposures. This is the core value of the
feature; without it nothing else matters.

**Independent Test**: Run a default scan against a workspace containing an
`application.properties` file with a plaintext `db.password=...` entry and
confirm the file is reported as an unprotected finding, while a sibling
`.properties` file containing only non-secret settings is not reported.

**Acceptance Scenarios**:

1. **Given** a workspace with `application.properties` containing
   `spring.datasource.password=hunter2`, **When** an operator runs a default
   scan, **Then** the file is reported as an unprotected finding.
2. **Given** a `.properties` file whose only entries are non-secret settings
   (for example `server.port=8080`), **When** a scan runs, **Then** the file is
   not reported as a finding.
3. **Given** a `.properties` file with multiple entries where exactly one has a
   secret-indicating name and a plaintext value, **When** a scan runs, **Then**
   the file is reported once and the operator can identify which property
   triggered the finding.
4. **Given** a property `ssl.key.file=/path/to/id_rsa` pointing to an
   unprotected key file inside the authorized scope, **When** a scan runs,
   **Then** the referenced key file is assessed and reported as unprotected.

---

### User Story 2 - Avoid False Positives on Externalized or Encrypted Values (Priority: P1)

As an operator who already follows good practice (externalizing secrets to
environment variables, vaults, or encrypting them in place), I want properties
whose secret-named values are placeholders, references, encrypted, or empty to
NOT be reported, so that the scan stays trustworthy and actionable instead of
drowning me in noise.

**Why this priority**: A secret scanner that flags correctly-externalized
configuration is worse than none — operators stop trusting it. Precision is as
important as detection for adoption.

**Independent Test**: Run a scan against a `.properties` file containing a
secret-named property set to a placeholder reference (for example
`db.password=${DB_PASSWORD}`), a separate entry with an encrypted wrapper, and a
blank entry; confirm none are reported, while a sibling plaintext secret in the
same file is reported.

**Acceptance Scenarios**:

1. **Given** a property `db.password=${DB_PASSWORD}` (placeholder/externalized
   reference), **When** a scan runs, **Then** that property is not reported.
2. **Given** a property whose value uses a recognized encrypted-value wrapper
   (for example a `ENC(...)`-style encrypted value), **When** a scan runs,
   **Then** that property is not reported.
3. **Given** a secret-named property with an empty value (for example
   `password=`), **When** a scan runs, **Then** that property is not reported.
4. **Given** a secret-named property whose value is an obvious non-secret (for
   example `password.min.length=8` or `auth.secret.enabled=true`), **When** a
   scan runs, **Then** that property is not reported because it fails the
   credential-likeness heuristics.

---

### User Story 3 - Customize Which Property Names Are Treated as Secrets (Priority: P2)

As an operator with organization-specific naming conventions, I want to control
the set of property-name patterns that mark a property as secret-bearing through
configuration, so I can add internal conventions (for example `corp_token`) or
narrow the set to reduce noise without patching the tool.

**Why this priority**: Naming conventions vary by team and language ecosystem.
Configurability is the operational payoff, but the shipped defaults already
deliver value, so this is secondary to detection itself.

**Independent Test**: Add a custom property-name pattern to a test
configuration, run a scan over a `.properties` file using that convention with a
plaintext value, and confirm it is reported; remove a default pattern and
confirm the corresponding property is no longer reported.

**Acceptance Scenarios**:

1. **Given** the shipped configuration, **When** an operator inspects it,
   **Then** they find a complete, commented list of the default property-name
   patterns treated as secret-bearing.
2. **Given** a configuration that sets the property-name pattern list with one
   or more entries, **When** a scan runs, **Then** only those patterns mark a
   property as secret-bearing (replace semantics), and omitting the key uses the
   packaged defaults.
3. **Given** the property-name pattern list explicitly set to an empty array,
   **When** a scan runs, **Then** `.properties` content inspection performs no
   property-name matching (no properties are flagged on name grounds).

---

### User Story 4 - Never Expose the Secret Value (Priority: P2)

As an operator who may share or store scan output, I want findings to identify
the file and the offending property by name and location only, never echoing the
secret value itself, so that running the scanner does not itself leak the
credential into logs, terminals, or CI artifacts.

**Why this priority**: A security tool must not become a secret-exfiltration
path. This is a safety guardrail on the output of US1–US3.

**Independent Test**: Run a scan over a `.properties` file with a plaintext
secret and capture all output streams; confirm the secret value string never
appears in any stream while the file path and offending property name do.

**Acceptance Scenarios**:

1. **Given** a reported plaintext secret property, **When** the operator reviews
   all scan output, **Then** the file path and the offending property key are
   present and the secret value is absent.

---

### Edge Cases

- **Comments and blank lines**: Lines that are comments (starting with `#` or
  `!`) or blank MUST NOT be treated as properties.
- **Separator variants**: Entries may use `=`, `:`, or whitespace as the
  key/value separator, and values may contain additional `=`/`:` characters.
- **Line continuations**: A value continued across lines with a trailing
  backslash MUST be assembled into a single logical value before assessment.
- **Whitespace**: Leading/trailing whitespace around keys and values is
  insignificant and MUST be trimmed before matching and assessment.
- **Key casing**: Property-name matching MUST be case-insensitive (for example
  `Password`, `PASSWORD`, `db.passWord` all match a `password` pattern).
- **Name match but non-secret value**: A secret-named property whose value is an
  obvious non-secret (for example `password.min.length=8`,
  `password.required=true`) MUST NOT be reported, because the value fails the
  credential-likeness heuristics even though the key name matches.
- **Value referencing an external key file**: A secret-named property whose
  value is a filesystem path to a key file (for example
  `ssl.key.file=/etc/app/id_rsa`) MUST be resolved and the referenced file
  assessed; the file is reported when the referenced key material is
  unprotected. Relative paths resolve against the `.properties` file's own
  directory. A path that cannot be resolved or lies outside authorized scope is
  handled gracefully (see FR-007).
- **Inline key material**: A property value that itself contains key material
  (for example an inline PEM block) MUST be assessed for protection like other
  embedded key material.
- **Ignored properties files**: A `.properties` file whose path matches an
  existing ignore rule MUST NOT be inspected.
- **Duplicate keys**: When the same key appears more than once, each occurrence
  is assessed; the file is reported if any qualifying occurrence is found.
- **Unreadable or malformed file**: A `.properties` file that cannot be read or
  decoded MUST be surfaced through the existing malformed-file reporting path,
  not silently skipped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include Java `.properties` files among the files
  selected for evaluation during a default scan, subject to the same authorized
  traversal and ignore rules as other candidates.
- **FR-002**: System MUST parse `.properties` file content into individual
  property entries (key, value, source line) following standard properties
  syntax: `=`/`:`/whitespace separators, `#`/`!` comment lines, blank lines, line
  continuations, and insignificant surrounding whitespace.
- **FR-003**: System MUST identify property entries whose key matches the
  configured set of secret-indicating name patterns (default set includes, at
  minimum, names equivalent to `password`, `pass`, `passwd`, `pwd`, `secret`,
  `private`, `key`, `token`, `credential`, and `apikey`), using
  case-insensitive matching.
- **FR-004**: For each secret-named property entry, System MUST report it as an
  unprotected finding only when the value passes the credential-likeness
  heuristic, which requires BOTH a minimum length AND a minimum
  entropy/character-diversity threshold (exact bounds finalized in planning).
  Values that are pure booleans, pure integers, or otherwise below either
  threshold MUST NOT be reported. Inline key material is assessed under FR-006
  regardless of these thresholds.
- **FR-005**: System MUST NOT report a secret-named property whose value is
  empty, a placeholder/externalized reference (for example `${...}`, `@...@`,
  `#{...}`), or wrapped in a recognized encrypted-value form (for example
  `ENC(...)`).
- **FR-006**: System MUST assess a property value that contains inline key
  material as it assesses other embedded key material, reporting it when
  unprotected.
- **FR-007**: When a secret-named property value is a filesystem path to a key
  file, System MUST resolve the path and assess the referenced file's protection
  using the existing key-material classification, reporting it when unprotected.
  Relative paths MUST be resolved against the directory of the `.properties` file
  that contains the reference. A reference that cannot be resolved (missing file)
  or resolves outside the authorized traversal scope MUST be handled without
  aborting the scan and without following it as a finding.
- **FR-008**: System MUST NOT emit any property value to any output stream;
  findings identify the file path and the offending property key/location only.
- **FR-009**: System MUST emit one finding on the canonical-path output stream
  per offending property, using a `<file path>#<property key>` form so each
  finding is independently identifiable, with corresponding per-property detail
  in the stderr summary.
- **FR-010**: The set of secret-indicating property-name patterns MUST be
  configurable with omit/empty/replace semantics consistent with the project's
  existing pattern configuration (omitting the key uses packaged defaults; an
  empty list disables name matching; a non-empty list replaces the defaults).
- **FR-011**: System MUST honor existing ignore rules so that a `.properties`
  file under an ignored directory or matching an ignored filename pattern is
  never inspected.
- **FR-012**: System MUST surface `.properties` files that cannot be read or
  decoded through the existing malformed-file reporting path.
- **FR-013**: A key file reached only by following a property reference (FR-007)
  MUST count toward `files_scanned` exactly once and MUST be deduplicated against
  the same file when it is also discovered directly by the traversal, so totals
  never double-count.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and infrastructure concerns,
  and MUST comply with SOLID, Clean Code, DRY, and KISS.
- **NFR-002**: Feature MUST describe required unit tests that validate the
  change, any needed integration or contract tests, and the expected
  coverage-report impact; after implementation the full unit-test suite and
  coverage report are run, with any failing test triaged (test logic vs.
  implementation logic) before the test or code is changed.
- **NFR-003**: Feature MUST remain compliant with the project's linting,
  formatting, and static analysis gates.
- **NFR-004**: Feature MUST state whether standalone packaging, entry points,
  release artifacts, or deployment documentation change.

### Key Entities *(include if feature involves data)*

- **Properties File Candidate**: A discovered `.properties` file selected for
  content inspection; carries its canonical path.
- **Property Entry**: A single parsed key/value pair with its source location;
  the unit against which name matching and value assessment are applied.
- **Secret-Name Pattern Set**: The configurable collection of name patterns that
  mark a property key as secret-bearing.
- **Value Assessment**: The determination of whether a property value is an
  unprotected plaintext secret, an externalized/encrypted/empty value (not a
  finding), or inline key material (assessed for protection).
- **Finding**: A reported exposure tying a properties file (and offending
  property location) to an unprotected secret, without the secret value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a validation dataset, 100% of `.properties` files containing a
  plaintext secret under a default secret-name pattern are reported in a default
  scan with no manual configuration.
- **SC-002**: In the same dataset, 0% of `.properties` files whose secret-named
  values are exclusively externalized, encrypted, or empty are reported (no
  false positives on those entries).
- **SC-003**: Across all scan output streams, the secret value string for a
  reported property appears 0 times, while the file path appears for every
  finding.
- **SC-004**: An operator can change which property names are treated as secrets
  entirely through configuration, with no tool modification, and verify the
  effect on the next scan.
- **SC-005**: Adding `.properties` content inspection does not require any
  additional directory traversal beyond the existing single walk (targeted reads
  of key files referenced by FR-007 excepted), and per-file inspection cost
  scales linearly with file size.

## Assumptions

- **Format scope**: Only Java-style `.properties` files are in scope for this
  feature. Other configuration formats (YAML, XML, `.ini`, `.cfg`, `.env`) are
  out of scope here; `.env` files remain covered by their existing handling.
- **Name matching**: Property-name patterns match case-insensitively as a
  substring/glob against the full property key, so dotted keys such as
  `spring.datasource.password` match a `password` pattern. The exact default
  catalog and any narrowing comments are finalized during planning.
- **Externalized/encrypted forms**: Placeholder references (`${...}`, `@...@`,
  `#{...}`) and recognized encrypted wrappers (`ENC(...)`) represent good
  practice and are intentionally not reported.
- **Credential-likeness heuristics**: A value is credential-like only when it
  meets BOTH a minimum length and a minimum entropy/character-diversity
  threshold; pure booleans and integers never qualify. The exact numeric bounds
  are finalized during planning, but the combined length-and-entropy gate is
  fixed by this spec.
- **Key-file reference resolution**: Following a property value as a path reuses
  the existing authorized-scope and key-material classification rules; relative
  paths resolve against the referencing `.properties` file's directory, the scan
  never reads files outside the configured traversal scope, and missing or
  unresolvable references degrade gracefully.
- **Configuration model**: The secret-name pattern set follows the same
  omit/empty/replace configuration semantics already established for ignore
  patterns (see feature 007), and the packaged example configuration documents
  the defaults.
- **Output model**: Findings continue to use the existing path-on-stdout,
  summary-on-stderr model; each offending property yields one stdout finding in
  `<file path>#<property key>` form, conveying the property identifier without
  the secret value.
- **Reuse of classification**: Inline key material found inside a property value
  reuses the existing key-material protection assessment rather than a new
  parser.
