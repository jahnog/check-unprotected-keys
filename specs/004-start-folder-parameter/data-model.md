# Data Model: Start Folder Parameter

## Start Folder Parameter (CLI Concept)

**Purpose**: Optional user-supplied value on the command line that designates a directory from which (or beneath which) the configured key search should be launched. It acts as a scope limiter for the folder patterns only; filename patterns are never altered.

**Representation** (in the running system):
- Received from the CLI as a raw string (`args.start_folder` or `None` when omitted).
- Resolved by the domain into either `None` (omitted / full scope) or a canonical `Path` (valid start folder).

**Validation Rules** (derived from FR-001..FR-005 and the acceptance scenarios):
- The parameter is strictly optional.
- When present, it MUST be interpretable as a path (relative or absolute, with `~` expansion).
- Relative paths are resolved against the execution root (current working directory at invocation time).
- After resolution the candidate MUST exist, MUST be a directory, and MUST be readable (`os.access(..., R_OK)`).
- On any failure the whole invocation fails early with a clear actionable error; no configuration is loaded and no scan is performed.

**State Transitions**:
- Omitted (`None` from argparse) → full-scope search launch.
- Valid value → narrowed scope search launch.
- Invalid value → error path (exit 2, diagnostic on stderr, zero findings on stdout).

## Validation Result for Start Folder

**Purpose**: The outcome of checking a supplied (or omitted) start-folder value. This is the primary "unit-testable" artifact for the four required cases (passed, omitted, valid, invalid).

**Success Outcome**:
- `None` when the parameter was omitted → caller treats as "no narrowing".
- `Path` (resolved, absolute, canonical) when the value was valid → caller uses it to narrow the effective roots.

**Error Outcomes** (all surfaced as `ValueError` with specific message text that the CLI turns into user-visible diagnostics):
- "Start folder does not exist: <resolved>"
- "Start folder is not a directory: <resolved>"
- "Start folder is not readable: <resolved>"

**Validation Rules**:
- Exactly one of success or error is produced for any input.
- Error messages contain the final resolved path so the operator can see what was actually evaluated.
- No secret material or file contents ever appear in error messages.

## Effective Search Scope (Narrowed by Start Folder)

**Purpose**: The concrete set of root directories and filename patterns that will actually be walked for a given invocation. When a valid start-folder is supplied, this scope is a (possibly proper) subset of the configured scope.

**Key Fields** (from `EffectiveScope`):
- `root_directories: tuple[Path, ...]` — the narrowed set (may be empty if the start folder does not overlap any configured folder patterns).
- `filename_patterns: tuple[str, ...]` — always the full configured set (start-folder never filters filename patterns).
- `canonical_root_set: frozenset[Path]` — used for duplicate suppression.

**Invariants** (relevant to start-folder):
- `filename_patterns` are copied verbatim from configuration.
- Every directory in `root_directories` is at or beneath the start-folder (when one was supplied and valid).
- The narrowing logic is deterministic and idempotent.

**Relationship to Other Concepts**:
- Produced by `resolve_effective_scope(configuration, start_folder=...)` which first expands configured folder patterns then calls `narrow_root_directories(..., start_folder=...)` + `build_effective_scope(...)`.
- Consumed by `discover_candidate_files` and the scan service.
- `ScanRequest` carries the raw resolved `start_folder: Path | None` from the CLI all the way to the service/adapters so that the narrowing decision can be made after configuration is loaded (but after the early validation in `resolve_start_folder`).

## ScanRequest (Carrier)

**Purpose**: Bundles everything needed for one scan invocation, including the (already validated) start-folder value.

**Relevant Field**:
- `start_folder: Path | None = None`

This field is set directly from the return value of `resolve_start_folder` (or left as `None`).

## Summary of Data Flow for the Parameter

1. CLI receives raw string (or absent) → calls `resolve_start_folder(execution_root, raw)`.
2. On success → `ScanRequest(..., start_folder=resolved_or_none)`.
3. Later, `resolve_effective_scope` uses the `start_folder` value (if any) to produce a narrowed `EffectiveScope`.
4. All subsequent discovery and classification works against the narrowed scope while preserving filename patterns.
5. Unit tests for steps 1-2 are the new coverage required by this feature; downstream narrowing already has unit coverage.

All text and path values that cross the CLI/domain boundary for this feature MUST remain secret-safe.