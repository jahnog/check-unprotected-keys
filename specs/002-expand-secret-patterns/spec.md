# Feature Specification: Expand Secret Patterns

**Feature Branch**: `[002-expand-secret-patterns]`

**Created**: 2026-06-05

**Status**: Draft

**Input**: User description: "expand the folder and filename patterns to include other commonly used files to store public, private or api keys or user secrets that can be unencrypted."

## Clarifications

### Session 2026-06-05

- Q: Should this feature only expand default patterns, or also add detection for generic plaintext API keys, tokens, and user secrets? → A: Expand patterns only; findings remain limited to the tool's current supported exposure detection, including supported key material embedded in matched text files.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Broaden Default Secret Coverage (Priority: P1)

As a security-conscious operator, I want the default scan configuration to cover
more of the common folders and filenames where key material and text files that
may embed supported key material are kept so that routine scans find exposed
material without requiring me to expand the configuration first.

**Why this priority**: Missed locations or filenames reduce trust in the tool's
default coverage and increase the chance that exposed material remains
undetected.

**Independent Test**: Run a default scan against a validation dataset that
contains exposed material under newly covered folders and filenames, then
confirm those files are evaluated and reported without any manual configuration
changes.

**Acceptance Scenarios**:

1. **Given** the product ships with an expanded baseline configuration,
   **When** the user runs a default scan, **Then** files stored under the newly
   covered common secret-storage locations and naming conventions are evaluated
   as part of that scan.
2. **Given** a dataset includes exposed material under conventions that were not
   previously covered by the shipped defaults, **When** the scan runs with the
   expanded baseline, **Then** affected files using those conventions are
   reported without the operator adding custom patterns first.

---

### User Story 2 - Expand Coverage Without Excess Noise (Priority: P2)

As an operator, I want the broader baseline patterns to stay focused on likely
key-bearing locations and filenames so that expanded coverage does not flood
the scan with unrelated files.

**Why this priority**: Coverage is valuable only if the results remain usable;
an overly broad baseline would make the tool expensive to trust and review.

**Independent Test**: Run the scan against a mixed dataset containing common
in-scope storage conventions and clearly unrelated files, then verify that the
expanded baseline includes the intended categories without duplicating or
spamming results.

**Acceptance Scenarios**:

1. **Given** a directory tree contains both likely in-scope files and
  unrelated files, **When** the scan runs with the expanded defaults,
  **Then** the scan includes files in the supported key-storage and text-file
  categories
   and excludes unrelated naming conventions outside the documented baseline.
2. **Given** multiple expanded folder or filename conventions reach the same
   file, **When** the scan completes, **Then** that file is evaluated once and
   reported at most once.

---

### User Story 3 - Preserve Operator Control (Priority: P3)

As a maintainer or operator, I want the broader baseline patterns to remain
configuration-driven and compatible with start-folder narrowing so that I can
adopt, trim, or target the expanded defaults without changing code.

**Why this priority**: The baseline must be useful across different
environments, and operators need to control scope without losing consistency.

**Independent Test**: Update the configuration to add or remove some of the
expanded patterns, rerun the scan with and without a valid start folder, and
verify that the next scan respects both the edited configuration and the
existing narrowing behavior.

**Acceptance Scenarios**:

1. **Given** the baseline configuration contains expanded folder and filename
   patterns, **When** an operator edits that configuration, **Then** the next
   scan reflects those additions or removals without requiring source changes.
2. **Given** an operator supplies a valid start folder, **When** the scan runs
   with the expanded defaults, **Then** only matching locations beneath that
   start folder are searched while the expanded filename patterns remain
   unchanged.

### Edge Cases

- Sensitive files are stored under hidden tool directories or nested workspace
  configuration folders that were previously outside the default scan scope.
- Generic names such as `credentials`, `config`, `auth`, or `secrets` appear in
  both sensitive and non-sensitive contexts.
- A single file matches multiple newly added folder or filename patterns.
- A covered file contains a mixture of public material, protected private keys,
  exposed private keys, or unsupported secret formats.
- An operator intentionally removes some of the expanded baseline categories in
  a local configuration and should not have those choices overwritten.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an expanded baseline set of folder
  patterns covering common local locations used for SSH material,
  cloud-provider credentials, infrastructure or deployment configuration,
  container or orchestration configuration, and other workstation or project
  directories where supported key material is commonly stored.
- **FR-002**: The system MUST provide an expanded baseline set of filename
  patterns covering common names and extensions used for private keys,
  certificate or key bundles, credential files, environment files, and other
  text files where supported key material is commonly embedded.
- **FR-003**: The system MUST apply the expanded baseline patterns during a
  default scan without requiring operators to manually add them first.
- **FR-004**: The system MUST keep folder-pattern and filename-pattern
  definitions operator-visible and editable through the configuration file.
- **FR-005**: The system MUST preserve existing start-folder semantics so that a
  start-folder override narrows reachable folder matches only and does not
  alter the expanded filename pattern set.
- **FR-006**: The system MUST continue to evaluate each affected file once per
  scan even when it is reached through multiple expanded folder or filename
  patterns.
- **FR-007**: The system MUST continue to report only files that meet the
  product's supported exposure criteria, including supported key material
  embedded in matched text files, and MUST not treat inclusion by a new pattern
  as a finding by itself or add generic plaintext API-key, token, or unsupported
  secret detection as part of this feature.
- **FR-008**: The system MUST document the expanded baseline coverage so that an
  operator can understand which folder and filename conventions are included by
  default.
- **FR-009**: The system MUST allow operators to remove, replace, or further
  expand the baseline patterns through configuration without requiring source
  changes.
- **FR-010**: The expanded baseline MUST use curated pattern categories instead
  of broad catch-all scope that would scan unrelated filesystem content by
  default.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: The feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and filesystem or parsing
  adapters.
- **NFR-002**: The feature MUST include unit tests for default pattern loading
  and effective-scope resolution, plus integration or contract tests for
  default scan behavior and start-folder compatibility, with coverage reporting
  for the changed behavior.
- **NFR-003**: The feature MUST remain compliant with the project's linting,
  formatting, and static analysis quality gates.
- **NFR-004**: The feature MUST document any changes to shipped configuration
  examples, operator guidance, or standalone runtime expectations caused by the
  expanded baseline patterns.

### Key Entities *(include if feature involves data)*

- **Baseline Pattern Set**: The shipped folder and filename conventions that
  define the default scan scope before any operator customization.
- **Pattern Category**: A documented grouping of related locations or filenames
  such as SSH material, cloud credentials, deployment secrets, or environment
  files.
- **Effective Scan Scope**: The reachable set of folders and filenames after
  combining the baseline configuration, any operator edits, and the optional
  start-folder override.
- **Candidate File**: A file selected by the effective scope because its
  location or name suggests it may contain supported exposed material.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a validation dataset containing exposed material in at least 8
  newly supported naming or location conventions, the default scan reports 100%
  of affected files without any manual configuration edits.
- **SC-002**: An operator can adopt the expanded baseline by using one shipped
  configuration file and can identify the documented coverage categories within
  5 minutes.
- **SC-003**: When a valid start folder is supplied, 100% of reported findings
  come from matching locations within that limited scope while the expanded
  filename patterns remain in effect.
- **SC-004**: Overlapping expanded patterns produce zero duplicate file reports
  in the reference validation dataset.
- **SC-005**: In a mixed validation dataset of newly covered key-bearing,
  text-container, and unrelated files, the expanded defaults surface supported
  exposed material from all documented baseline categories without requiring
  root-wide catch-all scanning.

## Assumptions

- This feature expands the shipped search-scope patterns rather than defining a
  new exposure model for generic plaintext API keys, tokens, or other secret
  types outside the product's current supported classification rules.
- Operators can continue tailoring the configuration for their environment by
  removing or adding pattern entries.
- The initial baseline should prioritize broadly used local workstation and
  repository conventions for Linux-first environments.
- Remote secret stores, encrypted vault products, and service-side secret
  inventories remain out of scope.
- Public-key-only files may still appear in scope when their naming conventions
  overlap with mixed-content files, but public material alone is not a finding.
