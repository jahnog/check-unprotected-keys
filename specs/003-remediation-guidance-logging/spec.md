# Feature Specification: Remediation Guidance Logging

**Feature Branch**: `[003-remediation-guidance-logging]`

**Created**: 2026-06-05

**Status**: Draft

**Input**: User description: "also log to console the malformed files. and for the unprotected files, suggest what will be the best method to protect the key affecting ass less ass possible the software development workflow (i.e. using system vault that asks for a vault password once per session). verify what is the normal usage of each file and propose the best slution for it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surface Malformed File Paths (Priority: P1)

As an operator reviewing scan results, I want the scanner to explicitly list the
malformed files it could not fully evaluate so that I can inspect or clean up
those files instead of relying only on a summary count.

**Why this priority**: Files that cannot be parsed are a direct review gap.
Operators need the exact paths immediately in order to decide whether the files
are harmless, corrupted, or require manual remediation.

**Independent Test**: Run a scan over a dataset containing malformed files and
confirm that the console output includes each malformed file path in an
operator-safe way while preserving the existing finding-path stream.

**Acceptance Scenarios**:

1. **Given** a scan encounters one or more malformed files, **When** the scan
   completes, **Then** the console output identifies each malformed file path in
   addition to the aggregate malformed-file summary.
2. **Given** a scan encounters malformed files and valid unprotected findings,
   **When** the scan completes, **Then** malformed-file logging does not prevent
   affected files from being reported or change the meaning of the existing exit
   codes.

---

### User Story 2 - Recommend Low-Friction Protection Methods (Priority: P2)

As an operator handling unprotected key findings, I want the scanner to suggest
the most appropriate protection method for each affected file based on its
likely usage so that I can secure the key with minimal disruption to the normal
development or runtime workflow.

**Why this priority**: A finding is more actionable when the tool also explains
how to protect it in a way that fits the key's apparent role instead of forcing
operators to invent a remediation plan from scratch.

**Independent Test**: Run a scan over representative SSH, service, deployment,
and embedded-key fixtures, then confirm the console guidance recommends a
workflow-appropriate protection approach for each affected file.

**Acceptance Scenarios**:

1. **Given** a finding path and naming convention strongly suggest an
   interactive user key, **When** the scan reports the finding, **Then** the
   console guidance recommends a session-oriented protection approach that keeps
   day-to-day interactive use practical.
2. **Given** a finding path or file context suggests automation, deployment, or
   embedded configuration usage, **When** the scan reports the finding, **Then**
   the console guidance recommends a protection approach appropriate for that
   operational context instead of generic one-size-fits-all advice.

---

### User Story 3 - Preserve Scriptable Output and Operator Trust (Priority: P3)

As a maintainer or automation user, I want the additional malformed-file logs
and remediation suggestions to remain compatible with existing CLI usage so that
human-facing guidance becomes richer without breaking machine-readable finding
consumption.

**Why this priority**: The scanner already has a defined console contract.
Additional guidance is valuable only if it preserves operator trust and does not
break existing scripts or review workflows.

**Independent Test**: Run the scan through current CLI contract scenarios and
verify that affected file paths remain machine-readable while malformed-file
logs and remediation suggestions appear in the operator-facing console channel.

**Acceptance Scenarios**:

1. **Given** a scan produces unprotected findings, malformed files, or both,
   **When** the command completes, **Then** the machine-readable finding-path
   stream remains stable and the additional guidance is emitted separately as
   operator-facing console output.
2. **Given** a scan produces no findings but does encounter malformed files,
   **When** the command completes, **Then** the command still communicates the
   malformed review gap clearly without misreporting affected files.

### Edge Cases

- A malformed file path resembles a high-value key location but contains only
  partial, truncated, or unsupported key material.
- A finding path is ambiguous, such as a generic `identity`, `.pem`, or `.key`
  file stored in a shared project directory with no obvious usage label.
- A file contains embedded private-key material in a text container used by
  automation, where a passphrase prompt could break unattended workflows.
- The same affected file matches multiple catalog patterns but should still
  receive one remediation recommendation.
- Public-only files or already protected keys are in scope and must not receive
  unprotected-key remediation guidance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST log the canonical path of each malformed file the
  scan could not fully evaluate.
- **FR-002**: The system MUST keep malformed-file path logging separate from the
  machine-readable affected-file path stream so that existing automated
  consumers can continue to read findings safely.
- **FR-003**: The system MUST continue to emit aggregate malformed and unreadable
  summaries after the scan completes.
- **FR-004**: The system MUST provide a remediation recommendation for each
  unprotected finding.
- **FR-005**: The system MUST tailor remediation recommendations according to
  the finding's likely usage category, including at minimum interactive user
  keys, service or deployment keys, and embedded-key configuration files.
- **FR-006**: The system MUST prefer low-friction protection approaches in its
  guidance, including session-oriented unlock workflows for interactive keys
  when that minimizes repeated prompts during normal use.
- **FR-007**: The system MUST recommend non-interactive protection approaches
  for likely automation, deployment, or embedded-configuration contexts when an
  interactive prompt would be operationally disruptive.
- **FR-008**: The system MUST explain remediation guidance using only
  operator-safe metadata such as file path, naming convention, and likely usage
  category, and MUST NOT echo secret material or raw file contents.
- **FR-009**: The system MUST continue to report only currently supported
  unprotected key findings and MUST NOT expand this feature into generic token,
  password, or unsupported secret detection.
- **FR-010**: The system MUST document how malformed-file logging and
  remediation guidance appear in the CLI output so operators can distinguish
  findings, review gaps, and next-step advice.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: The feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and infrastructure concerns.
- **NFR-002**: The feature MUST include unit tests for malformed-file logging
  and recommendation selection, plus integration or contract tests covering CLI
  output separation and guidance behavior, with coverage reporting for changed
  behavior.
- **NFR-003**: The feature MUST remain compliant with the project's linting,
  formatting, and static analysis gates.
- **NFR-004**: The feature MUST document any CLI output, operator guidance, or
  standalone artifact behavior changes caused by malformed-file logging and
  remediation suggestions.

### Key Entities *(include if feature involves data)*

- **Malformed Scan Issue**: A file the scanner could not classify because the
  content was unreadable as supported key material even though it matched scan
  scope.
- **Remediation Recommendation**: Operator-facing advice that describes the most
  appropriate way to protect an unprotected key while minimizing workflow
  disruption for its likely usage.
- **Usage Category**: A human-meaningful label inferred from file path or file
  context, such as interactive SSH key, service credential, deployment key, or
  embedded configuration secret.
- **Operator Output Channel**: The human-facing console stream used for
  summaries, malformed-file logs, and remediation guidance while leaving the
  finding-path stream stable for automation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a validation dataset containing malformed files, 100% of
  malformed file paths are surfaced in operator-facing console output during the
  scan.
- **SC-002**: In a validation dataset containing representative interactive,
  service, deployment, and embedded-key findings, 100% of unprotected findings
  receive a remediation recommendation tied to an explicit usage category.
- **SC-003**: Existing CLI contract validation continues to pass with zero
  regressions in machine-readable finding-path output.
- **SC-004**: An operator can determine the likely remediation path for each
  reported unprotected finding within 1 minute of reading the scan output,
  without consulting external documentation.

## Assumptions

- Remediation recommendations are advisory guidance only; this feature does not
  automatically rotate, encrypt, move, or rewrite keys.
- The scanner can infer enough likely usage context from file location, naming
  convention, and whether the key is embedded in a text container to provide a
  useful default recommendation.
- Interactive user keys generally benefit from a session-scoped unlock workflow,
  while automation-oriented keys generally need protection approaches that do
  not depend on a human prompt for every execution.
- Additional malformed-file logging and remediation guidance should be emitted
  in operator-facing console output rather than mixed into the machine-readable
  finding path stream.