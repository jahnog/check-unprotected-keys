# Data Model: Search Bases and Directory Hints (Broad Discovery)

## SearchConfiguration (Evolved)

**Purpose**: The authoritative source of what trees the scanner is allowed to explore and how it should discover high-value subdirectories and prune noise.

**Fields** (additions and evolution from prior specs):

- `config_file_path`: Path to the `.check-unprotected-keys.toml` that was loaded.
- `execution_root`: Canonical path of the directory from which the CLI was invoked (used for relative resolution).
- `base_folders`: tuple[str, ...] — the primary list of search bases (ancestor trees). Replaces or is the documented successor to the old `folder_patterns` for new usage. Each entry may be relative to execution_root, absolute, or contain `~`.
- `directory_names`: tuple[str, ...] — simple basenames used for automatic promotion of high-value directories under the bases. Examples: `".ssh"`, `"secrets"`, `"deploy"`, `"keys"`, `"certs"`, etc. No glob metacharacters are required or processed for these entries.
- `ignore_directories`: tuple[str, ...] — basenames of directories that must never be descended (during promotion discovery or candidate enumeration). Ships with a useful default set in the packaged example; user config can extend or replace per documented rules.
- `filename_patterns`: tuple[str, ...] — **unchanged** in semantics. These continue to select candidate files (by basename fnmatch) once a directory is being walked. They are never altered by start-folder or by the new base/hint logic.

**Validation Rules** (in addition to prior rules):

- At least one of `base_folders` or the legacy `folder_patterns` key must be present and non-empty (compat).
- When `base_folders` is present it must be a non-empty array of strings (after the compat bridge).
- `directory_names` and `ignore_directories`, when present, must be arrays of non-blank strings.
- All pattern strings are trimmed on load. Blank or whitespace-only entries are rejected with a clear `ConfigurationError`.
- No semantic validation of "this name makes sense" is performed at load time (a name that never matches is harmless).

**Backward Compatibility Note**:

During a transition period the loader accepts the legacy `folder_patterns` key. In the absence of an explicit `base_folders` key the legacy value is treated as the set of bases (and, as a convenience, simple bare names from that list may be automatically contributed to the effective directory hints for that run). After migration users should prefer the clearer `base_folders` + `directory_names` spelling.

## ScanRequest (Unchanged Core)

**Purpose**: Carries one invocation, including the optional narrowing directive.

**Relevant Field** (unchanged):

- `start_folder: Path | None`

The start-folder value (when present) is applied *after* initial base expansion but *during* the promotion and final narrowing steps. It limits which bases participate and which subdirectories are considered for promotion.

## EffectiveScope (Evolved)

**Purpose**: The concrete, deduplicated set of directories that will be walked plus the (always full) filename rules.

**Fields** (evolved):

- `root_directories: tuple[Path, ...]` — the final canonical directories from which `discover_candidate_files` will `os.walk`. This set is the union of:
  - Resolved and narrowed bases.
  - Promoted directories discovered under those bases via `directory_names` (subject to ignores and start-folder).
- `filename_patterns: tuple[str, ...]` — copied verbatim from configuration (never filtered by start-folder or by hints).
- `canonical_root_set: frozenset[Path]` — used for duplicate suppression (unchanged).
- (Optional but recommended for richer provenance) `base_set: frozenset[Path]` and/or a mapping from promoted root to the hint + originating base that produced it. Consumers such as `infer_usage_category` and malformed logging can use this to produce better `matched_folder_pattern` strings.

**Invariants**:

- Every path in `root_directories` is absolute and canonical.
- Duplicates (from overlapping bases, a base that is also a promoted dir, etc.) are collapsed.
- `filename_patterns` is always the complete configured set.
- An empty `root_directories` after start-folder narrowing is a valid (no-op) scope; it is not a configuration error.
- Pruning is applied uniformly: no directory whose basename is in the active ignore set ever appears in `root_directories` or is descended during discovery.

**Relationship to Discovery**:

`resolve_effective_scope(configuration, start_folder=...)` now performs three logical phases:
1. Base expansion (adapt the prior `_expand_folder_pattern` logic to the `base_folders` list).
2. Promotion discovery under the (start-folder-narrowed) bases using the `directory_names` list while skipping `ignore_directories`.
3. Final assembly + deduplication into `EffectiveScope`.

The old `narrow_root_directories` helper is reused / extended for the start-folder interaction over both bases and promoted results.

## CandidateFile (Minor Evolution)

**Purpose**: Represents a single file selected for key-material assessment.

**Fields** (existing + guidance on `matched_folder_pattern`):

- `canonical_path`, `display_path`, `state` — unchanged.
- `matched_folder_pattern: str` — previously stored the string form of the root directory that caused the file to be considered. In the new model this field (or a companion) SHOULD convey provenance such as:
  - The base that authorized the walk (e.g. "base:.")
  - The directory hint that promoted the containing directory (e.g. "hint:secrets")
  - Or a compact combined form: "base:., hint:deploy"
- `matched_filename_pattern: str` — unchanged (the fnmatch pattern that selected the basename).

Downstream code (`infer_usage_category` in the scan service, malformed issue recording, and any future reporting) already lowercases and performs substring / equality checks against this field. Enriching the value with "base:" / "hint:" prefixes is safe and improves the quality of automation-hint detection and `.ssh` special cases without requiring changes to those call sites initially.

## Promotion & Pruning Concepts (New First-Class Ideas)

**Directory Name Promotion**:
- Performed after base expansion and start-folder narrowing.
- For each active base, for each name in `directory_names`, locate subdirectories (at any depth) whose `Path.name` exactly equals the hint (or fnmatch if we later decide to allow simple globs — start with exact for simplicity and predictability).
- Results are collected, filtered by the active ignore set, resolved to canonical form, and unioned with the bases themselves.
- Promotion is best-effort: permission errors during the name search are recorded as `DiscoveryIssue`s (existing mechanism) and do not abort the scan.

**Pruning**:
- Applies to *both* the promotion name search and the later `os.walk` performed by `discover_candidate_files`.
- Implemented efficiently via `os.walk(..., topdown=True)` and mutating the `dirnames` list in place, or by filtering glob results.
- Exact basename match only (no path components). This keeps the mental model simple: "anything named `node_modules` anywhere under my bases is ignored."
- The active ignore list for a run is: the documented defaults union (or replacement, per loader policy) the user-supplied `ignore_directories`.

**Why both bases *and* promoted dirs become roots**:
- Bases guarantee that any file whose *name* matches a `filename_pattern` (including the container formats `.env*`, `*.ovpn`, `*.tfvars` and the many `*_key`, `*.pem`, `privkey*` patterns) is evaluated no matter what directory it lives in.
- Promoted dirs give explicit "we know this kind of directory is high-signal" coverage and better `matched_folder_pattern` values for usage inference and operator diagnostics, even if the file inside happens to have a generic name that still matched a broad filename pattern.

## Relationships & Data Flow

1. `load_search_configuration` (config/loader.py) → `SearchConfiguration` (now with the three new tuple fields).
2. CLI constructs `ScanRequest(execution_root, configuration, start_folder=...)`.
3. `ScanService.run` calls `filesystem.resolve_effective_scope(request.configuration, start_folder=...)`.
4. The resolver:
   - Expands bases.
   - Calls (new) promotion logic under the bases (respecting start-folder and ignores).
   - Produces `EffectiveScope`.
5. `discover_candidate_files(scope)` walks the `root_directories`, applies `filename_patterns`, produces `CandidateFile` records (with improved `matched_folder_pattern`).
6. The rest of the pipeline (key parsing, `is_finding`, `infer_usage_category`, `ScanResult` aggregation, reporting) is unchanged in structure.

All secret material remains confined to the transient `CandidateFile` / assessment objects; nothing containing key bytes ever appears in `matched_folder_pattern`, error messages, or summaries.

## Summary of Changes to Prior Data Model (001/002/003/004)

- `folder_patterns` in the configuration model is now documented as the legacy spelling for bases. New code and docs prefer `base_folders`.
- `SearchConfiguration` gains two new curated lists (`directory_names`, `ignore_directories`) and a clearer name for the tree list.
- `EffectiveScope.root_directories` is now the *result* of base expansion + name-based promotion + pruning + start-folder narrowing (previously only pattern expansion + start-folder narrowing).
- `CandidateFile.matched_folder_pattern` gains a recommended richer format while remaining a string (no new type introduced in this feature).
- No changes to `ProtectionClassification`, `UsageCategory`, `ScanResult`, `KeyFinding`, or the core assessment types.
- `DiscoveryIssue` (already existed for walk errors) is also used for promotion-time unreadable locations.

This evolution preserves the "filename patterns are the recall mechanism; classification suppresses noise" philosophy while making the *location* side of scope resolution far more ergonomic for broad but controlled searches.