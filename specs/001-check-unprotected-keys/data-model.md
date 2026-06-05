# Data Model: Check Unprotected Keys

## SearchConfiguration

**Purpose**: Defines the authoritative folder and filename patterns used to
derive the scan scope.

**Fields**:

- `config_file_path`: canonical path to `.find-unencrypted-keys.toml`
- `execution_root`: canonical path used as the default scan root
- `folder_patterns`: ordered list of non-empty folder glob strings
- `filename_patterns`: ordered list of non-empty filename glob strings

**Validation Rules**:

- `folder_patterns` MUST contain at least one entry.
- `filename_patterns` MUST contain at least one entry.
- Pattern strings MUST be trimmed and non-empty.
- Relative folder patterns are resolved from `execution_root`; absolute folder
  patterns remain absolute.

## ScanRequest

**Purpose**: Captures one invocation of the scanner.

**Fields**:

- `execution_root`: canonical path representing the default root for the scan
- `start_folder`: optional canonical path that narrows folder-pattern expansion
- `configuration`: reference to `SearchConfiguration`

**Validation Rules**:

- `execution_root` MUST exist and be readable.
- If provided, `start_folder` MUST exist and be readable before scanning starts.
- `start_folder` MUST NOT alter `filename_patterns`; it only filters effective
  folder matches.

## EffectiveScope

**Purpose**: Represents the folder set and filename rules actually applied for a
single scan.

**Fields**:

- `root_directories`: resolved folder roots after applying configuration and the
  optional `start_folder`
- `filename_patterns`: unchanged filename glob list from configuration
- `canonical_root_set`: deduplicated set of canonical root directories

**Validation Rules**:

- All `root_directories` are canonical absolute paths.
- Duplicate roots collapse into one canonical entry.
- An empty `root_directories` set is a valid no-op scan result, not a config
  error, when the supplied `start_folder` simply narrows the scope to nothing.

## CandidateFile

**Purpose**: Tracks a file chosen for evaluation.

**Fields**:

- `canonical_path`: canonical absolute path to the file
- `display_path`: string emitted to output when the file becomes a finding
- `matched_folder_pattern`: configuration rule that reached the file
- `matched_filename_pattern`: filename rule that matched the file
- `state`: lifecycle state of the evaluation

**Validation Rules**:

- `canonical_path` MUST identify a regular file.
- Each `canonical_path` appears at most once per scan.
- `display_path` MUST equal the canonical absolute path rendered for console
  output.

**State Transitions**:

- `DISCOVERED -> DUPLICATE_SKIPPED`
- `DISCOVERED -> UNREADABLE`
- `DISCOVERED -> CLASSIFIED`
- `CLASSIFIED -> REPORTED`
- `CLASSIFIED -> CLEAN`

## ProtectionAssessment

**Purpose**: Records the result of classifying supported key material in one
candidate file.

**Fields**:

- `classification`: one of `UNPROTECTED`, `PROTECTED_WITH_PASSPHRASE`,
  `PUBLIC_ONLY`, `MALFORMED`, or `UNREADABLE`
- `format_hint`: `pem`, `openssh`, `ppk`, `text-embedded`, or `unknown`
- `message`: operator-safe explanation without secret material

**Validation Rules**:

- `message` MUST NOT contain key contents, passphrases, or raw line values.
- `PROTECTED_WITH_PASSPHRASE` and `PUBLIC_ONLY` do not produce findings.
- `MALFORMED` and `UNREADABLE` contribute to summaries but not to the findings
  list.

## KeyFinding

**Purpose**: Represents a file-level violation emitted to stdout.

**Fields**:

- `file_path`: canonical absolute path
- `classification`: currently limited to `UNPROTECTED`

**Validation Rules**:

- One `KeyFinding` exists per affected file, even if multiple offending keys are
  present.
- `classification` MUST map to an exit code that signals findings.

## ScanResult

**Purpose**: Aggregates all outcomes from one scan.

**Fields**:

- `files_scanned`: count of unique candidate files evaluated
- `findings`: ordered list of `KeyFinding`
- `malformed_count`: count of malformed candidate files
- `unreadable_count`: count of unreadable candidate files
- `exit_code`: `0`, `1`, or `2`

**Validation Rules**:

- `exit_code = 1` when `findings` is non-empty.
- `exit_code = 0` when the scan completes without findings and without a fatal
  invocation/configuration error.
- `exit_code = 2` when configuration loading or CLI validation fails before the
  scan can execute.

## Relationships

- One `SearchConfiguration` feeds many `ScanRequest` executions.
- One `ScanRequest` produces one `EffectiveScope`.
- One `EffectiveScope` produces zero or more `CandidateFile` records.
- Each `CandidateFile` yields at most one `ProtectionAssessment`.
- `ScanResult` aggregates zero or more `KeyFinding` records plus non-finding
  summary counts.