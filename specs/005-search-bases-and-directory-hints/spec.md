# Feature Specification: Search Bases and Directory Hints (Broad Discovery)

**Feature Branch**: `[005-search-bases-and-directory-hints]`

**Created**: 2026-06-09

**Status**: Draft

**Input**: User request to support broader discovery without forcing maintainers to maintain a large list of explicit `**/foo` (or equivalent) entries in `folder_patterns`. The current "high-precision folder roots only" model (bare names resolve only as direct children of the execution root) results in very few effective roots and "only checks 4 files" even when many more candidates exist under common directory names scattered through a tree. The desired alternative design is "Search Bases + Directory Name Hints + Pruning".

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

### User Story 1 - Search Bases Define Authorized Trees (Priority: P1)

As a security operator, I want to declare one or more "search bases" (ancestor directories or globs such as ".", "src", "~/work", or specific monorepo roots) so that the scanner is authorized to explore entire subtrees under them and apply filename patterns (plus embedded key detection) to any matching files found anywhere beneath those bases.

**Why this priority**: This is the foundational shift that enables broad discovery. A small number of explicit bases replaces the previous need to list every possible leaf directory that might contain keys. It directly addresses the "only checks 4 files" symptom when running against real projects that have keys scattered under many subdirectories.

**Independent Test**: Configure a broad base (e.g. a temp workspace root or "fixtures"), place key material (by name or embedded) at various depths including non-obvious paths, run a scan, and verify that filename-matched candidates are discovered and evaluated from the full depth of the base (not just direct children).

**Acceptance Scenarios**:

1. **Given** `base_folders` contains one or more entries (relative, absolute, or `~`-prefixed), **When** the scan runs, **Then** the effective roots include the resolved bases and the scanner walks their subtrees applying the configured filename patterns.
2. **Given** a base such as "." or a project root, **When** the scan completes, **Then** files whose names match `filename_patterns` (including containers like `.env*`, `*.ovpn`, `*.tfvars`) are evaluated for key material even if they live many directories deep or in unlisted subdirectories.
3. **Given** multiple overlapping bases, **When** the scan runs, **Then** each unique canonical directory is walked only once (deduplication is preserved).

---

### User Story 2 - Directory Name Hints Enable Automatic Promotion (Priority: P1)

As an operator who knows common directory names that hold secret material (".ssh", "secrets", "keys", "deploy", "infra", "certs", "tls", "pki", "ansible", etc.), I want to list those names once in a `directory_names` array so that the scanner automatically discovers matching subdirectories anywhere under my configured bases — without me having to write `**/secrets`, `**/deploy`, etc. for each one.

**Why this priority**: This eliminates the maintenance burden of explicit `**/` entries while still giving operators a high-signal way to ensure important directories are covered and categorized. It is the direct solution requested for "broader discovery without a huge list of explicit **/foo entries".

**Independent Test**: Provide a base + a `directory_names` list containing both shallow and deep names; populate a workspace with key material inside `apps/api/secrets/`, `services/bar/deploy/`, and a top-level `keys/`; verify that the promoted directories are included in effective roots (or that candidates under them are found) and that `matched_folder_pattern` on candidates reflects the hint.

**Acceptance Scenarios**:

1. **Given** `directory_names` lists simple basenames (no globs required) and `base_folders` is configured, **When** the scan runs, **Then** any subdirectory whose basename matches a directory name (at any depth under a base, subject to pruning) is discovered and contributes to the scan scope.
2. **Given** a promoted directory (e.g. "secrets"), **When** candidates are produced from it, **Then** the `matched_folder_pattern` (or enriched equivalent) identifies both the originating base and the hint that caused promotion.
3. **Given** a filename match occurs directly under a base or in a non-hinted subdirectory, **When** the candidate is created, **Then** it is still evaluated (bases themselves provide full subtree coverage via filename patterns).

---

### User Story 3 - Pruning Makes Broad Bases Practical (Priority: P1)

As an operator who wants to use broad bases such as "." or a large work directory, I want built-in, configurable directory pruning (with safe defaults for `.git`, `node_modules`, `.venv`, `target`, `dist`, `__pycache__`, etc.) so that the scanner does not waste time or produce excessive noise walking build artifacts, caches, and VCS directories.

**Why this priority**: Without pruning, broad discovery is unusable on real developer machines and monorepos. Pruning is a non-negotiable enabler for the P1 broad-bases story and must be present for the feature to deliver value.

**Independent Test**: Configure a broad base containing both interesting key directories and several well-known noise directories at various depths; run with default (and custom) ignore lists; verify that pruned directories are never descended and that no candidates are produced from inside them, while real key material elsewhere is still found.

**Acceptance Scenarios**:

1. **Given** the default (or user-supplied) `ignore_directories`, **When** discovery walks a base, **Then** any directory whose basename exactly matches an ignore entry is skipped (its subtree is not traversed for candidates or further promotion).
2. **Given** an `ignore_directories` override in the user's config, **When** the scan runs, **Then** the user's list is used (additive or replacing defaults per documented semantics) and pruning behavior is deterministic.
3. **Given** a hinted directory name that would otherwise be promoted, **When** it sits inside an ignored parent, **Then** it is not discovered or walked (ignores win).

---

### User Story 4 - Backward Compatibility and Migration (Priority: P2)

As a maintainer with an existing `.check-unprotected-keys.toml` that uses the old `folder_patterns` style (many bare names or a few specific subdirs), I want the tool to continue to function after an upgrade, with a clear, low-friction migration path to the new `base_folders` + `directory_names` model.

**Why this priority**: The change is a semantic evolution of `folder_patterns`. Existing users must not be surprised by total breakage; the system should either treat old `folder_patterns` as bases (with optional auto-promotion of their simple names) or provide helpful errors + documentation.

**Independent Test**: Load a config that only contains the legacy `folder_patterns` key (no `base_folders`); run scans in both narrow and broader workspaces; verify that behavior is at least as good as before (or improved via promotion) and that no hard failure occurs on upgrade.

**Acceptance Scenarios**:

1. **Given** a config using only the legacy `folder_patterns` key, **When** the scanner loads it, **Then** the entries are interpreted as bases (or a documented compat bridge exists) and the scan proceeds without a ConfigurationError.
2. **Given** an old-style config with many bare directory names, **When** the new promotion logic is active, **Then** those names are also treated as directory hints (or the example migration produces an equivalent `directory_names` list) so that broader discovery "just works" for common cases.
3. **Given** a user who has migrated to the new keys, **When** both legacy and new keys are present, **Then** the documented precedence is clear and the behavior is deterministic.

---

### User Story 5 - Start-Folder Continues to Narrow Correctly (Priority: P2)

As an operator using `--start-folder` for targeted investigations, I want the parameter to continue to limit scope (now over bases and the promotion search under them) while leaving filename patterns unchanged.

**Why this priority**: `--start-folder` is an established, documented, and tested feature (spec 004). The new broader model must not regress or surprise users who rely on it.

**Independent Test**: Use existing start-folder contract/integration tests plus new scenarios with broad bases + hints; supply a `--start-folder` that is a subtree; verify that only candidates under the start folder (including only promoted dirs under it) are considered, and that the "Checked N" and findings counts reflect the narrowed scope.

**Acceptance Scenarios**:

1. **Given** `--start-folder` points inside a base, **When** the scan runs, **Then** effective roots are further narrowed to those at or under the start folder (both base roots and promoted directory roots respect the limit).
2. **Given** `--start-folder` is supplied, **When** directory name promotion runs, **Then** promotion search is performed only under the intersection of bases and the start folder.
3. **Given** a start folder that matches no bases or promoted dirs, **When** the scan completes, **Then** zero candidates are produced and the result is a clean (or zero-finding) run with appropriate messaging.

---

### Edge Cases

- Base folder entries that resolve to the same canonical directory (dedup must still occur).
- Directory name hints that are substrings or overlap with ignore names (ignores take precedence; documented).
- Using "." or very high bases together with `--start-folder` deep inside a large tree.
- Home-expanded bases (`~`) + promotion under them.
- Promotion discovery performance on very large trees (mitigated by pruning; may warrant future depth or time bounds).
- Old configs that list both shallow and `**/`-style entries during the compat window.
- `matched_folder_pattern` / usage inference continuing to work (and improving) for automation hints, `.ssh` detection, etc.
- Empty or near-empty `directory_names` (bases still provide full filename-based coverage).
- Interaction with `MALFORMED` / noise files when walking broad bases (the existing stderr summary + PUBLIC_ONLY filtering remains the safety valve; pruning reduces volume).
- Symlinks (current `followlinks=False` behavior should be preserved).
- Permission errors during promotion discovery vs. during the main candidate walk (both should be collected as issues without aborting the whole scan).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The configuration loader MUST accept (and the resolver MUST act on) a `base_folders` (or compat `folder_patterns`) array that defines the ancestor trees under which scanning is authorized.
- **FR-002**: The system MUST support a `directory_names` array of simple basenames; during scope resolution it MUST discover (promote) any subdirectories under the (narrowed) bases whose basename matches an entry, without requiring the user to supply glob metacharacters.
- **FR-003**: The system MUST support an `ignore_directories` array (with documented safe defaults) and MUST skip any directory whose basename matches an ignore entry during both promotion discovery and candidate enumeration.
- **FR-004**: When `base_folders` (or legacy) are resolved, the effective `root_directories` fed to `discover_candidate_files` MUST include the bases themselves (so that filename patterns catch material at any depth) in addition to any promoted directories.
- **FR-005**: The `--start-folder` parameter (and its existing validation + narrowing logic) MUST continue to work and MUST narrow both the set of active bases and the promotion search performed under them; filename patterns remain unchanged.
- **FR-006**: Backward compatibility MUST be provided so that a config containing only the legacy `folder_patterns` key loads and produces at least the same (or broader, thanks to promotion) results as before the change.
- **FR-007**: `CandidateFile.matched_folder_pattern` (and the corresponding fields on `MalformedScanIssue`) MUST continue to be populated with a useful string; the implementation SHOULD enrich it to reflect the originating base and/or the directory hint that caused a file to be reached.
- **FR-008**: All new configuration keys (`base_folders` / `directory_names` / `ignore_directories`) MUST follow the same validation rules as existing pattern arrays (non-empty when present, strings only, trimmed, no blank entries) unless explicitly relaxed in the contract.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: The architecture MUST keep the concerns separated: config loading & validation, scope resolution / promotion discovery (adapters/filesystem + domain/scope), candidate enumeration, classification, and reporting.
- **NFR-002**: New or changed behavior (especially the promotion and pruning logic, and the new config surface) MUST be accompanied by unit tests, contract tests, and/or integration tests that cover the happy paths, error/edge paths, and interaction with `--start-folder`. Overall coverage MUST not fall below the 85% gate; new code is expected to increase exercised branches.
- **NFR-003**: The feature MUST remain compliant with the project's linting, formatting, static analysis, and test gates (exact commands defined in plan.md and pyproject.toml).
- **NFR-004**: No changes to the public CLI entry point name, PyInstaller spec, or release artifacts are required for the core capability. Documentation (README, example config, help text where relevant) MUST be updated.
- **NFR-005**: Pruning and promotion discovery MUST be efficient enough that using a modest number of bases (including ".") on typical developer machines and small-to-medium monorepos is practical. Excessive noise on stderr from broad walks is mitigated by pruning + the existing MALFORMED/PUBLIC_ONLY filtering.
- **NFR-006**: The change is additive / evolutionary. Existing narrow configs that listed specific subdirectories as "folder_patterns" should continue to produce similar (or improved) results.

### Key Entities *(include if feature involves data)*

- **Search Base (Base Folder)**: A configured entry (from `base_folders` or legacy `folder_patterns`) that represents an ancestor tree the operator authorizes the scanner to explore. Resolved to one or more canonical directories.
- **Directory Name Hint**: An entry from the `directory_names` list. A simple basename used to automatically locate and promote matching subdirectories under bases as high-value locations.
- **Promoted Directory**: A subdirectory discovered because its basename matched a directory name hint. It becomes (or contributes to) an effective root for candidate enumeration.
- **Ignore Directory Name**: An entry from `ignore_directories`. Directories matching these are never descended during promotion or candidate walks.
- **Effective Search Scope**: The final set of `root_directories` (bases + promoted) plus the unchanged `filename_patterns` after base expansion, promotion, pruning, and start-folder narrowing.
- **Matched Folder Provenance**: The information recorded on a `CandidateFile` (and malformed issues) that tells later stages (usage inference, logging) which base and/or hint was responsible for reaching the file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a single broad `base_folders = ["."]` (or equivalent) + a realistic `directory_names` list + default ignores, a workspace containing key material at multiple arbitrary depths under common names (secrets/, deploy/, keys/, etc.) plus keys named according to filename patterns in other locations, the scanner discovers and evaluates candidates from all of them (files_scanned reflects the true set of matching files under the base, modulo pruning).
- **SC-002**: No `**/ ` or complex globs are required in user configuration to achieve the discovery described in SC-001; the `directory_names` list uses only simple basenames.
- **SC-003**: Default (and user-overridable) pruning prevents descent into at least the common noise directories (`.git`, `node_modules`, `.venv`, `target`, `dist`, `__pycache__`, etc.) and no candidates are produced from inside ignored subtrees.
- **SC-004**: Existing configs using only the legacy `folder_patterns` key continue to load and run (compat path); after a simple migration to the new keys the observable behavior for the same material is the same or broader.
- **SC-005**: All pre-existing `--start-folder` contract and integration tests continue to pass (or have minimal, clearly justified updates). New start-folder scenarios with broad bases demonstrate correct narrowing of both bases and promotion.
- **SC-006**: Dedicated tests (unit + supporting contract/integration) exist for: base expansion, directory name promotion (including deep nesting), pruning (default + override), the interaction of bases + hints + start-folder, and the compat/migration path. Coverage of the new resolution and discovery paths increases.
- **SC-007**: The "Checked N file(s)" summary, findings on stdout, and malformed/unreadable guidance on stderr remain exactly as before for narrow usage; for broad usage they reflect the larger (but still useful) set of candidates with no secrets leaked.
- **SC-008**: Full project quality gates (ruff, format, pyright, pytest with 85% cov) pass after the change.

## Assumptions

- The primary goal is *broader but still user-controlled* discovery. Operators explicitly list the bases they care about; the tool does not default to walking the entire machine or home directory.
- Full subtree walking under a base (governed by filename patterns + content parsing + pruning) is the mechanism that delivers "any file that looks like a key container anywhere under my project" recall. Directory name hints are an accelerator for common high-value locations and for richer metadata/categorization.
- The existing `filename_patterns` + embedded block detection (PEM, OpenSSH, PuTTY, etc.) + MALFORMED classification on stderr remain the primary tools for controlling noise. Broad bases will naturally surface more MALFORMED items; pruning + operator-chosen bases keep this manageable.
- `matched_folder_pattern` can be evolved from a simple root label string to a slightly richer provenance string without breaking downstream consumers (it is already used for diagnostics, usage inference, and malformed logging).
- The change is large enough to warrant a new spec (005) and updates to the 001-era data model and config contract, but small enough that the core `os.walk` + `fnmatch` + classification pipeline is reused with a better set of roots.
- No new runtime dependencies are introduced.
- The duplicate legacy package tree under `src/find_unencrypted_keys/` (old name before the rename to `check_unprotected_keys`) will be removed as part of this work for cleanliness.

## Notes on Scope

Out of scope for this feature (can be future work):
- Automatic respect for `.gitignore` (a secret scanner often wants to see gitignored material; explicit `ignore_directories` is the provided control).
- Content-based or ML-based discovery of "any private key bytes anywhere" (the tool remains name + known container + known block based).
- Hard performance caps (depth, time, file count) on promotion or walking — pruning is the first-line control.
- Changes to the standalone executable build or release process.
- Altering the strict stdout-only-for-findings contract.