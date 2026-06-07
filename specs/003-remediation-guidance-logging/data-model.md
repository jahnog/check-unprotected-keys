# Data Model: Remediation Guidance Logging

## UsageCategory

**Purpose**: Classifies the likely operational role of an unprotected finding so
the scanner can emit the least disruptive secure recommendation.

**Values**:

- `interactive-user-key`
- `ssh-host-key`
- `automation-or-deployment-key`
- `embedded-config-secret`
- `unknown`

**Validation Rules**:

- A finding MUST receive exactly one `UsageCategory`.
- Category inference MUST use only operator-safe metadata such as path,
  matched-pattern context, and file-container type.
- Category inference MUST NOT depend on raw secret contents.

## RemediationRecommendation

**Purpose**: Stores the operator-facing advice attached to one unprotected
finding.

**Fields**:

- `usage_category`: the inferred `UsageCategory`
- `title`: short label for the recommended protection path
- `summary`: one-line recommendation safe for console display
- `rationale`: short explanation of why the recommendation fits this usage
- `next_step_hint`: concise operational next step the user can take

**Validation Rules**:

- All text fields MUST be safe to print to stderr.
- `summary` and `next_step_hint` MUST avoid raw secret values, passphrases, or
  file contents.
- Recommendations for `ssh-host-key` MUST NOT require an interactive passphrase
  prompt during normal service startup.

## MalformedScanIssue

**Purpose**: Represents one candidate file that matched scan scope but could not
be fully parsed as supported key material.

**Fields**:

- `file_path`: canonical absolute path for operator review
- `issue_type`: stable safe label such as `malformed`
- `matched_folder_pattern`: resolved folder pattern that reached the file
- `matched_filename_pattern`: filename pattern that admitted the file

**Validation Rules**:

- `file_path` MUST be canonical and absolute.
- Each malformed candidate path MUST appear at most once per scan result.
- `issue_type` MUST remain secret-safe and suitable for aggregate summaries.

## KeyFinding

**Purpose**: Represents one stdout finding plus its stderr-only remediation
metadata.

**Fields**:

- `file_path`: canonical absolute path emitted to stdout
- `classification`: existing protection classification
- `usage_category`: inferred `UsageCategory`
- `remediation`: `RemediationRecommendation` for operator-facing guidance

**Validation Rules**:

- Only unprotected findings receive remediation guidance.
- `file_path` MUST remain identical to the canonical path printed to stdout.
- The presence of `usage_category` or `remediation` MUST NOT change exit-code
  behavior.

## ScanResult

**Purpose**: Aggregates the data required to render findings, malformed-file
review gaps, and safe issue summaries for one CLI invocation.

**Fields**:

- `files_scanned`: count of candidate files inspected
- `findings`: ordered list of `KeyFinding`
- `malformed_issues`: ordered list of `MalformedScanIssue`
- `unreadable_count`: aggregate unreadable-file count
- `error_summaries`: stable map of safe issue labels to counts

**Derived Values**:

- `exit_code`: `1` when `findings` is non-empty, otherwise `0`
- `malformed_count`: length of `malformed_issues`
- `safe_issue_breakdown`: sorted tuple view of `error_summaries`

**Validation Rules**:

- `findings` MUST preserve discovery order for stable output.
- `malformed_issues` MUST preserve discovery order for stable operator review.
- Stdout rendering MUST consume only `findings.file_path`.
- Stderr rendering MAY consume summaries, `malformed_issues`, and remediation
  data but MUST remain secret-safe.

## Relationships

- One `KeyFinding` maps to exactly one `UsageCategory` and one
  `RemediationRecommendation`.
- One `ScanResult` contains zero or more `KeyFinding` and zero or more
  `MalformedScanIssue` entries.
- `MalformedScanIssue` and `KeyFinding` are both derived from the existing
  candidate-discovery and classification pipeline, but only `KeyFinding`
  influences the exit code.