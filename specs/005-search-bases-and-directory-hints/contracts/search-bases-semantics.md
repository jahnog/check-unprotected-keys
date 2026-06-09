# Contract: Search Bases, Directory Hints, and Pruning Semantics

**Feature**: 005-search-bases-and-directory-hints  
**Related**: specs/001-check-unprotected-keys/contracts/config-contract.md (primary config contract — this document supplements it)

## Purpose

Define the observable contract for the new configuration surface (`base_folders`, `directory_names`, `ignore_directories`) and the resulting effective scope, promotion, and pruning behavior. This is the authoritative description for implementers, test authors, and future maintainers who need to know exactly what the loader and resolver must do without reading the full implementation.

## Configuration Keys (under `[scan]`)

### `base_folders` (preferred spelling)

- Type: array of strings (required for new-style configs; see Legacy below).
- Semantics: Each entry is a *search base* — an ancestor directory (or glob) that the operator authorizes the scanner to explore.
- Resolution:
  - `~` is expanded via `Path.expanduser()`.
  - Relative entries are resolved against the execution root (the directory containing the `.check-unprotected-keys.toml` / `Path.cwd()` at invocation).
  - Absolute entries are used as-is.
  - Glob metacharacters are supported (same rules as the prior folder pattern expansion).
  - Only directories that exist after expansion are retained.
- After start-folder narrowing (when supplied), only the subset of bases that are at or under (or that contain) the start folder participate in promotion and candidate enumeration.
- The resolved bases themselves become part of the effective `root_directories` (subject to deduplication). This guarantees that any file whose basename matches a `filename_pattern` anywhere under a base is considered, regardless of the directory name it lives in.

### `directory_names`

- Type: array of strings (optional but recommended for broad bases).
- Semantics: Simple basenames used to *automatically discover and promote* high-value subdirectories under the active bases.
- Matching: Exact basename match (`path.name == hint`). No glob expansion is performed on these entries in the initial implementation.
- Discovery occurs after base expansion and after start-folder narrowing has been applied to the bases.
- Promoted directories are unioned with the bases to form the final `root_directories` passed to candidate discovery.
- A promoted directory may itself be under another promoted directory; the deepest (or all) are retained as roots as long as they are canonical-unique.
- The originating hint (and the base under which it was found) SHOULD be reflected in the `matched_folder_pattern` stored on `CandidateFile` and `MalformedScanIssue` records for files reached via that promoted directory.

### `ignore_directories`

- Type: array of strings (optional).
- Semantics: Basenames of directories that must never be descended, either during promotion name search or during the main candidate `os.walk`.
- Matching: Exact basename only.
- Precedence: Ignored directories are skipped even if their name also appears in `directory_names` (ignores win).
- Defaults: The packaged example config and the loader's effective defaults include a practical set (`.git`, `node_modules`, `.venv`, `venv`, `target`, `dist`, `build`, `__pycache__`, common IDE and cache directories, etc.). User-supplied values are additive to the defaults (or replace them — exact policy will be documented in the loader and quickstart).
- Pruning is applied uniformly to both the promotion phase and candidate enumeration for consistency.

### `filename_patterns`

- Unchanged from the 001 contract.
- Applied (via `fnmatch`) to basenames of files encountered while walking any effective root (base or promoted).
- Never filtered by start-folder, base choice, or hints.

### Legacy Key: `folder_patterns`

- Still accepted by the loader when `base_folders` is absent (full backward compatibility for existing configs).
- Treated as the set of bases for resolution purposes.
- As a convenience during the transition, any entry in the legacy list that is a simple bare name (no `/` and no glob metacharacters) is also contributed to the effective `directory_names` for that run. This gives many existing "I listed a bunch of common dir names" configs broader discovery automatically.
- When both keys are present, the documented precedence (base_folders wins, or they are merged — to be finalized in implementation and recorded in research.md) applies. New documentation will strongly recommend migrating to the clearer `base_folders` + `directory_names` spelling.

## Effective Scope After Resolution

The resolver (`resolve_effective_scope`) produces an `EffectiveScope` whose `root_directories` is the deduplicated, canonical union of:

1. All resolved bases that survived start-folder narrowing.
2. All directories promoted because a subdirectory basename matched an entry in the active `directory_names`, discovered under the participating bases, and not excluded by the active ignore list.

`filename_patterns` in the scope is always the complete configured set.

An empty `root_directories` set after narrowing is valid and results in a no-op scan (0 files scanned, clean exit or zero findings).

## Candidate Provenance (`matched_folder_pattern`)

For every `CandidateFile` (and every `MalformedScanIssue`):

- The field continues to be a string.
- When a file is reached because a base authorized the walk, the value SHOULD identify the base (e.g. `"base:."` or `"base:repos/myproj"`).
- When the containing directory was promoted by a hint, the value SHOULD also identify the hint (e.g. `"base:., hint:secrets"` or `"base:infra, hint:deploy"`).
- The exact string format is an implementation detail but must be stable enough for the existing `infer_usage_category` logic (which already performs lower-case substring and equality checks for ".ssh", automation path hints, etc.) and for human-readable malformed logging.
- Files reached directly under a base (not inside a promoted hinted dir) still receive a useful base label so that usage inference and diagnostics remain informative.

## Start-Folder Narrowing Contract (unchanged from 004 + extended)

- Validation of the raw `--start-folder` value (`resolve_start_folder`) is performed early, before configuration is loaded, exactly as specified in spec 004 and `contracts/start-folder-validation.md`.
- The (validated or `None`) start folder is passed to the scope resolver.
- Narrowing affects *which bases participate* and *under which bases promotion is performed*.
- The classic "start folder replaces a parent root" and "keep only nested roots" behaviors from spec 004 continue to apply to bases.
- Promoted directories that are not at or under the start folder are excluded.
- `filename_patterns` are never affected.

## Error & Edge Handling (observable)

- Configuration errors for the new keys follow the same style and produce the same `ConfigurationError` + exit 2 path as today (blank entries, wrong types, empty required arrays, etc.).
- Promotion-time or walk-time permission errors are collected as `DiscoveryIssue`s (existing mechanism) and contribute to the unreadable / error summary on stderr; they do not abort the scan.
- A hinted directory that sits inside an ignored parent is never discovered or walked.
- Duplicate canonical paths (a base that is also promoted, overlapping bases, etc.) are collapsed exactly once.

## Relationship to Existing Contracts

- This document supplements, and does not replace, `specs/001-check-unprotected-keys/contracts/config-contract.md`.
- The CLI contract (`specs/001-check-unprotected-keys/contracts/cli-contract.md`) and the focused start-folder validation contract from spec 004 remain authoritative for `--start-folder`, `--print-example-config`, error emission, stdout vs stderr rules, and exit codes.
- The "Checked N file(s). Found M violation(s)." summary format, the rule that only real findings appear on stdout, and the treatment of MALFORMED / UNREADABLE on stderr are unchanged.

## Testable Invariants (for contract & unit authors)

1. A config with only legacy `folder_patterns` loads and runs (compat).
2. With a broad base + realistic `directory_names`, candidates are produced for key material both inside hinted directories at arbitrary depth *and* for files whose names match `filename_patterns` outside any hinted directory (as long as they are under a base).
3. Adding a name to `ignore_directories` causes every directory with that exact basename (at any depth under the bases) to contribute zero candidates and zero promotion.
4. Supplying `--start-folder` that is a subtree of a base produces a strictly smaller (or equal) set of effective roots and a correspondingly smaller or equal `files_scanned` count compared with the same config without the flag.
5. `matched_folder_pattern` values for candidates under promoted dirs contain both base and hint information in a form that the existing usage-inference code can still consume.

Any implementation that satisfies the scenarios in spec.md and the invariants above, while passing the full quality gates and the pre-existing start-folder + default-scan contract/integration suites, fulfills this contract.