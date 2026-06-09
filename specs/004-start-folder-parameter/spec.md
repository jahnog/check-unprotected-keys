# Feature Specification: Start Folder Parameter

**Feature Branch**: `[004-start-folder-parameter]`

**Created**: 2026-06-08

**Status**: Draft

**Input**: User description: "Verify that passing an optional start-folder parameter in the command line will launch the search from that start folder. also add unit tests to verify the functionality with the parameter is passed, is omitted, is valid and is invalid."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Narrow Search Scope via Start Folder (Priority: P1)

As a security operator or developer, I want to pass an optional start-folder parameter on the command line so that the search for unprotected keys is launched from (scoped to) only that starting folder and its subtree.

**Why this priority**: This is the primary requested behavior. Enabling a narrowed launch point delivers immediate value for targeted investigations without altering shared configuration.

**Independent Test**: Prepare a workspace with configured folders containing findings both inside and outside a chosen subtree; invoke the tool supplying the start-folder for the subtree only; verify that only findings under the supplied folder are reported.

**Acceptance Scenarios**:

1. **Given** the command line includes a valid optional start-folder parameter, **When** the command is executed, **Then** the search is launched from that start folder and only candidate locations within or under it are evaluated.
2. **Given** a valid start-folder is supplied and the subtree contains unprotected keys matching filename patterns, **When** the scan completes, **Then** the reported findings are limited to files under the start folder while filename patterns continue to apply.

---

### User Story 2 - Default Behavior When Parameter Omitted (Priority: P1)

As an operator performing routine checks, I want the start-folder parameter to be optional so that when it is omitted the search launches over the entire configured scope exactly as before.

**Why this priority**: Default usage (no parameter) must remain fully supported and produce unchanged results; this preserves existing workflows and confidence in the tool.

**Independent Test**: Run the identical configured scan once with the parameter omitted and once with an explicit start-folder that encompasses the full scope; confirm identical findings, counts, and exit codes.

**Acceptance Scenarios**:

1. **Given** the start-folder parameter is omitted from the command line, **When** the command runs, **Then** the search launches using the full set of configured folder patterns from the execution context.
2. **Given** the parameter is omitted on a clean or populated scope, **When** results are emitted, **Then** exit codes, stdout finding paths, and stderr summaries match the established unrestricted scan behavior.

---

### User Story 3 - Error on Invalid Start Folder Value (Priority: P2)

As an operator, I want the tool to reject an invalid start-folder value (path does not exist, is not a directory, or cannot be read) with a clear error so that no partial or misleading search is performed.

**Why this priority**: Failing fast on bad input prevents confusion and protects operators from believing a limited scan ran when it could not.

**Independent Test**: Invoke the CLI supplying a non-existent path, a regular file path, and (where test permissions allow) an unreadable directory as start-folder; verify error exit, diagnostic on stderr, empty stdout findings, and that scanning logic is never reached.

**Acceptance Scenarios**:

1. **Given** the supplied start-folder path does not exist on the filesystem, **When** the command processes the parameter, **Then** it reports an error, does not launch any search, and exits with a user-error status code.
2. **Given** the supplied start-folder exists but is not a directory or is not readable, **When** argument processing occurs, **Then** a clear error message is produced and the search is not launched.

---

### User Story 4 - Explicit Unit Test Coverage of Parameter States (Priority: P2)

As a maintainer, I want dedicated, executable unit tests that cover the start-folder parameter behavior for the specific cases of the parameter being passed, omitted, the value being valid, and the value being invalid.

**Why this priority**: Project constitution requires unit tests for changed or new behavior. Explicit unit-level verification of the four states (passed/omitted + valid/invalid) provides fast regression protection independent of contract or integration suites.

**Independent Test**: Execute only the unit tests written for start-folder parameter handling; observe that tests for each of the four combinations exist, are isolated, and pass, contributing positively to coverage metrics.

**Acceptance Scenarios**:

1. **Given** the unit test suite for start-folder handling, **When** the "parameter passed" (with a concrete value) tests execute, **Then** they verify that a supplied value causes the search to be launched from the indicated start folder.
2. **Given** the unit test suite, **When** the "parameter omitted" tests execute, **Then** they verify that the absence of the parameter results in the default full-scope search launch.
3. **Given** the unit test suite, **When** the "value is valid" tests execute, **Then** they confirm acceptance and correct use of a directory that exists and is readable.
4. **Given** the unit test suite, **When** the "value is invalid" tests execute, **Then** they confirm that non-existent paths, non-directories, and unreadable locations are rejected with appropriate error signaling before search launch.

---

### Edge Cases

- Start-folder supplied as a relative path that must be resolved against the current execution directory.
- Start-folder supplied as an absolute path.
- Start-folder that overlaps only a subset of configured folder patterns (partial narrowing).
- Start-folder that matches no configured folders (valid invocation producing zero candidates and clean exit).
- Start-folder at the filesystem root or a very large tree (performance/scoping implications remain out of scope for correctness).
- Interaction with configuration errors: invalid start-folder vs. missing or invalid configuration file (both should fail before search but may produce different messages).
- Paths requiring user home expansion or containing symlinks that resolve inside/outside the intended scope.
- Repeated or redundant start-folder values across multiple invocations.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI entry point MUST accept an optional start-folder parameter from the command line.
- **FR-002**: When a valid start-folder value is supplied, the system MUST launch the search scoped to that start folder (limiting which configured folders participate) while leaving filename patterns unchanged.
- **FR-003**: When the start-folder parameter is omitted, the system MUST launch the search using the complete set of configured folder patterns (full default scope).
- **FR-004**: The system MUST validate the start-folder value early; if the path does not exist, is not a directory, or is not readable, it MUST fail with a clear error message, MUST NOT launch any search activity, and MUST use an error-indicating exit code.
- **FR-005**: The start-folder parameter MUST accept both relative paths (resolved from execution context) and absolute paths.
- **FR-006**: The implementation of start-folder parameter handling MUST be accompanied by unit tests that explicitly verify behavior for the parameter when it is passed (with value), when it is omitted, when the value is valid, and when the value is invalid.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and infrastructure concerns.
- **NFR-002**: Feature MUST include unit tests for the start-folder parameter states (passed, omitted, valid, invalid). Existing contract tests and integration tests for start-folder scans MAY continue to exist but do not substitute for the required unit tests of the parameter handling logic itself. The change MUST not cause coverage to fall below configured project gates; new unit tests are expected to increase coverage of the exercised paths.
- **NFR-003**: Feature MUST remain compliant with the project's linting,
  formatting, and static analysis gates.
- **NFR-004**: Feature is additive to the existing CLI surface; no changes to standalone packaging, entry points, or release artifacts are required. Help text and any CLI contract documentation will reflect the (already present) option.

### Key Entities *(include if feature involves data)*

- **Start Folder Parameter**: The optional command-line value that designates the directory from which the key search should be launched. It acts as a scope limiter for folder patterns.
- **Effective Search Scope**: The resolved set of root directories and filename patterns actually used for a given invocation; this set is a subset of the configured scope whenever a start-folder is successfully applied.
- **Validation Result (for start folder)**: The outcome of checking the supplied parameter: either a usable directory reference enabling search launch, or an error condition that aborts before scanning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When a valid start-folder is passed, 100% of reported findings in acceptance and contract scenarios originate strictly from within the supplied start folder subtree (no leakage from outside the requested scope).
- **SC-002**: Omitting the start-folder parameter yields identical finding sets, file counts, exit codes (0/1/2), and output structure as the default unrestricted scan in all existing default-scan test cases.
- **SC-003**: Every invalid start-folder case (non-existent path, path to a file, unreadable directory) produces exit code indicating invocation error and a human-readable diagnostic on the error stream, with zero findings emitted on stdout and no search work performed.
- **SC-004**: Unit tests exist that separately and explicitly cover each of the four states (parameter passed, parameter omitted, value valid, value invalid); all such tests pass and the covered branches appear in the project's automated coverage report.
- **SC-005**: The --help output (and any user-facing documentation of options) includes the start-folder parameter so that operators discover the capability without reading source or tests.

## Assumptions

- "Start-folder parameter" refers to the optional command-line mechanism (already surfaced as --start-folder in help) that allows scoping the search launch point.
- "Launch the search from that start folder" means the effective folders searched become those that are at or beneath the supplied start folder; filename patterns are never altered by this parameter.
- When omitted, behavior is exactly the pre-existing full-scope scan (no change to defaults).
- Invalid values must be detected prior to loading configuration or performing any filesystem walking for keys; error must be actionable ("does not exist", "not a directory", etc.).
- Unit tests may live alongside existing unit modules or in a focused test module for scope/parameter resolution; the requirement is presence and isolation at unit level, not a specific file location.
- Relative paths are resolved relative to the process execution root (current working directory at invocation), consistent with other path handling in the tool.
- No new configuration file changes or environment variables are introduced by this feature; the parameter remains a pure CLI option.
- The feature primarily verifies and strengthens test coverage for behavior that supports the original product intent described in the 001 specification.
