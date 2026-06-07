# Feature Specification: Check Unprotected Keys

**Feature Branch**: `[001-check-unprotected-keys]`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "starting from the root folder, or from an optional start folder parameter, search common files that can store private or public keys (id_xxx, *.asx, .env, *.ppk, etc. ) and check if all the keys in them are protected with a non empty password or passphrase. if some keys are unprotected or protected with an empty password or empty passphrase, log that fact to console showing the full path and file name of the file. the list of folders and filename patterns to check should be stored in a configuration file, and those settings should be the ones where the search is performed. the optional start folder parameter will only limit the folders pattern where the search is performed, but the filename pattern remains."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect Unprotected Keys (Priority: P1)

As a security-conscious operator, I want to scan the configured search scope and
immediately see which files contain private key material that is unprotected or
protected with an empty password or passphrase.

**Why this priority**: This is the core value of the tool. Without reliable
identification of affected files, the application does not solve the primary
security problem.

**Independent Test**: Populate a controlled directory set with protected private
keys, unprotected private keys, empty-passphrase private keys, and public-only
key files, then run a default scan and verify that only affected files are
reported.

**Acceptance Scenarios**:

1. **Given** the configuration defines folder patterns and filename patterns,
   **When** the user runs the scan without a start folder, **Then** the system
   searches the configured scope and prints the full path of every file that
   contains an unprotected private key or a private key protected by an empty
   password or passphrase.
2. **Given** matching files contain only properly protected private keys or only
   public keys, **When** the scan completes, **Then** those files are not
   reported as violations.

---

### User Story 2 - Limit the Scan Scope (Priority: P2)

As an operator investigating one area of a filesystem, I want to provide an
optional start folder so that the scan only evaluates configured folders within
that area while keeping the configured filename patterns unchanged.

**Why this priority**: Operators often need a quicker, targeted check without
changing shared configuration that defines the overall search rules.

**Independent Test**: Prepare multiple configured scan areas, run the scan with
and without a valid start folder, and verify that findings are restricted to the
selected area while filename matching stays unchanged.

**Acceptance Scenarios**:

1. **Given** configured folder patterns match multiple locations, **When** the
   user supplies a valid start folder, **Then** the scan only evaluates matching
   folders beneath that start folder and still applies all configured filename
   patterns.
2. **Given** the user supplies a valid start folder that contains no matching
   configured folders or no candidate files, **When** the scan runs, **Then** it
   completes cleanly without reporting findings outside that limited scope.

---

### User Story 3 - Manage Search Patterns Through Configuration (Priority: P3)

As a maintainer, I want folder patterns and filename patterns to live in a
configuration file so that I can adjust what gets searched without changing the
application code.

**Why this priority**: Search scope will evolve over time, and keeping it in
configuration allows safer adaptation across teams and environments.

**Independent Test**: Update the configuration file to add and remove folder and
filename patterns, rerun the scan, and verify that the new scope is honored
without source changes.

**Acceptance Scenarios**:

1. **Given** the configuration file is updated with new folder or filename
   patterns, **When** the next scan runs, **Then** the updated settings define
   the scan scope.
2. **Given** overlapping patterns would otherwise reach the same file more than
   once, **When** the scan runs, **Then** each affected file is evaluated once
   and reported at most once.

### Edge Cases

- The provided start folder does not exist, is not readable, or does not map to
  any configured scan scope.
- A candidate file matches the configured patterns but contains malformed key
  material, unsupported encoding, or mixed content.
- A single file contains multiple keys with different protection states.
- The same file is reachable through overlapping folder patterns or symlinked
  paths.
- A matching file cannot be opened because of filesystem permissions.
- A file contains only public key material, which should not be treated as a
  passphrase violation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST load folder patterns and filename patterns from a
  configuration file and use those settings as the default scan scope.
- **FR-002**: The system MUST use the root folder as the starting scope when no
  start folder parameter is provided.
- **FR-003**: The system MUST accept an optional start folder parameter that
  narrows which configured folders are searched while leaving configured
  filename patterns unchanged.
- **FR-004**: The system MUST inspect each candidate file that matches the
  effective search scope to determine whether it contains private key material
  that requires password or passphrase protection.
- **FR-005**: The system MUST classify any private key with no password or
  passphrase, or with an empty password or passphrase, as a finding.
- **FR-006**: The system MUST not report files that contain only public key
  material as protection violations.
- **FR-007**: The system MUST print each finding to the console using the full
  path of the affected file.
- **FR-008**: The system MUST report an affected file at most once per scan,
  even if the file contains multiple offending keys or matches multiple folder
  patterns.
- **FR-009**: The system MUST continue scanning remaining files when an
  individual candidate file cannot be fully evaluated, while surfacing that the
  file could not be fully checked.
- **FR-010**: The system MUST honor configuration changes on the next scan run
  without requiring source-code changes.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: The feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and filesystem or parsing
  adapters.
- **NFR-002**: The feature MUST include unit tests for scope resolution and key
  protection classification, plus integration tests for end-to-end scan flows,
  with coverage reporting for the changed behavior.
- **NFR-003**: The feature MUST remain compliant with the project's linting,
  formatting, and static analysis quality gates.
- **NFR-004**: The feature MUST document any changes to standalone executable
  behavior, runtime configuration, or console reporting expectations.

### Key Entities *(include if feature involves data)*

- **Scan Configuration**: Defines folder patterns, filename patterns, and scan
  defaults that determine which files are eligible for inspection.
- **Scan Request**: Represents a single scan invocation, including the root
  execution context and the optional start folder override.
- **Candidate File**: A file reached through the effective scan scope and queued
  for key inspection using its canonical full path and evaluation status.
- **Key Finding**: A result that records that a file contains at least one
  unprotected private key or a private key protected by an empty password or
  passphrase.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a reference dataset containing protected private keys,
  unprotected private keys, empty-passphrase private keys, and public-only key
  files, the scan reports 100% of files containing unprotected or
  empty-passphrase private keys and reports 0 files containing only public keys.
- **SC-002**: A user can run a default scan and receive full-path console output
  for every affected file in a single invocation without editing application
  code.
- **SC-003**: A user can change the scan scope by editing one configuration
  file, and the next scan reflects those folder and filename pattern changes
  without a rebuild or code change.
- **SC-004**: When a valid start folder is provided, 100% of reported findings
  come from matching locations within that limited scope while all configured
  filename patterns remain in effect.
- **SC-005**: On a representative dataset of 5,000 candidate files, the scan
  completes within 2 minutes while producing the same findings as a full manual
  verification set.

## Assumptions

- The configuration file is stored with the application and is available at
  runtime for every scan.
- Only local filesystem content is in scope for the initial release; remote
  secret stores and network locations are out of scope.
- Console output is the only required reporting channel for the initial release;
  structured export formats are out of scope.
- Files that cannot be read or parsed should be surfaced as incomplete checks
  without stopping the rest of the scan.
- Public keys may appear in configured file matches, but only private key
  material that should be passphrase-protected is considered a violation.