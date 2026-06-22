# Feature Specification: Move Ignore Patterns to Configuration

**Feature Branch**: `007-move-ignore-to-config`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "move the ignored files and folders patterns to the configuration files."

## Clarifications

### Session 2026-06-22

- Q: When a user explicitly sets `ignore_directories` or `ignore_filename_patterns` with one or more entries, how should those entries combine with the packaged defaults? → A: **Replace** — when the key is present with any entries, only the user's list applies (no packaged defaults merged). Omitting the key still loads packaged defaults.
- Q: When a file matches both an inclusion pattern (e.g. `id_rsa.pub` matches `id_*`) and an ignore pattern (e.g. `*.pub`), what should the scanner do? → A: **Ignore wins** — skip the file entirely (not read, not counted in `files_scanned`).
- Q: What should the packaged default `ignore_filename_patterns` catalog include? → A: **Minimal plus cache and packages** — the minimal public/certificate/keystore families, plus cache artifact files and package-manager artifact files; corresponding cache and package install directories are included in packaged default `ignore_directories`.
- Q: When a legacy configuration contains a partial `ignore_directories` list (from the old additive model), should the scanner warn at startup? → A: **Warn at load** — emit an actionable warning when the configured list appears to be a partial extension, recommending the operator copy packaged defaults and merge custom entries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect and Understand All Ignore Rules in One Place (Priority: P1)

As a security operator maintaining a scan configuration, I want every default rule that skips directories and files during discovery to be declared in my configuration file (and in the shipped example configuration), so I can see exactly what the scanner will skip without reading application source code or scattered documentation comments.

**Why this priority**: Transparency is the core motivation for this change. Operators cannot safely tune a security scanner when ignore behavior is split between hidden built-in lists and partial comments. Making ignores visible in configuration is prerequisite to meaningful customization.

**Independent Test**: Open only the packaged example configuration and the operator's own `.check-unprotected-keys.toml`. Verify that every directory and file pattern the scanner skips by default is listed under dedicated ignore keys with explanatory comments. No separate "built-in defaults" list should exist only in code.

**Acceptance Scenarios**:

1. **Given** a fresh installation with the packaged example configuration, **When** an operator reviews the `[scan]` section, **Then** they find a complete, commented list of default directory ignore patterns (for example VCS, dependency, build, cache, package install trees, and IDE directories) under `ignore_directories`.
2. **Given** the packaged example configuration, **When** an operator reviews file-related ignore rules, **Then** they find a complete, commented list of default file ignore patterns (for example public-only, certificate-only, unsupported keystore filenames, cache artifacts, and package-manager lock/archive files) under `ignore_filename_patterns`.
3. **Given** an operator who has never cloned the repository, **When** they read their configuration file and its header comments, **Then** they can explain which directories and files the scanner will skip during a default run.

---

### User Story 2 - Customize Ignore Behavior Through Configuration (Priority: P1)

As an operator scanning unusual project layouts, I want to extend or override ignore patterns in my configuration file so I can reduce noise (for example skipping vendor trees or local artifact folders) or stop ignoring specific paths when I deliberately want them scanned.

**Why this priority**: Moving patterns to configuration only delivers value if operators can change them. Customization is the operational payoff of externalizing ignores.

**Independent Test**: Copy the packaged default ignore lists into a test configuration, add a custom directory name and filename pattern, and run a scan; confirm decoy material under the new ignore rules is skipped while real findings elsewhere are still detected.

**Acceptance Scenarios**:

1. **Given** a user configuration that sets `ignore_directories` to the packaged defaults plus additional entries, **When** a scan walks a broad base, **Then** directories whose basename matches any entry in that list are never descended.
2. **Given** a user configuration that sets `ignore_filename_patterns` with one or more entries, **When** a file basename matches an ignore pattern, **Then** that file is not evaluated even if it would otherwise match an inclusion pattern in `filename_patterns`.
3. **Given** a directory name listed in both `directory_names` and `ignore_directories`, **When** a scan runs, **Then** the ignore entry wins and the directory is not descended.
4. **Given** a filename that matches both `filename_patterns` and `ignore_filename_patterns`, **When** a scan runs, **Then** the ignore entry wins, the file is not read, and it is not counted in `files_scanned`.

---

### User Story 3 - Disable Default Ignores When Needed (Priority: P2)

As an advanced operator performing a deliberate deep audit, I want to supply an empty ignore list in my configuration so I can turn off the shipped default skips for directories or files without patching the tool.

**Why this priority**: Power users occasionally need full visibility (for example auditing a `node_modules` tree or scanning public-key sidecar files for mislabeled private material). Empty-list semantics already exist for directory ignores and must remain predictable after the migration.

**Independent Test**: Set `ignore_directories = []` (and, separately, `ignore_filename_patterns = []`) in a test configuration; run against a workspace containing both noise directories/files and real findings; confirm ignored-by-default locations are now traversed or evaluated while scan completion and finding accuracy remain correct.

**Acceptance Scenarios**:

1. **Given** `ignore_directories` is explicitly set to an empty array, **When** a scan runs, **Then** no directory-name pruning is applied (unless other scope limits apply).
2. **Given** `ignore_filename_patterns` is explicitly set to an empty array, **When** a scan runs, **Then** no filename-based ignore filtering is applied, and files such as `id_rsa.pub` that match `filename_patterns` are read and classified (restoring pre-migration overlap behavior).
3. **Given** a configuration that omits an ignore key entirely, **When** a scan runs, **Then** the packaged default ignore list for that key is applied so behavior matches pre-migration expectations.

---

### User Story 4 - Upgrade Without Surprises (Priority: P2)

As a maintainer with an existing `.check-unprotected-keys.toml` from a prior release, I want the scanner to behave the same after upgrade even if my config does not yet declare the new ignore keys, so I am not forced to edit configuration immediately to preserve current scan results.

**Why this priority**: This is a configuration-surface refactor, not a behavior change for typical deployments. Regression safety preserves trust.

**Independent Test**: Run the current test suite's representative configurations (minimal legacy configs and modern broad-base configs) before and after the change; confirm equivalent findings and equivalent directory pruning; accept a lower `files_scanned` count when packaged file ignores skip overlap candidates (for example `id_rsa.pub`) that were previously read and classified as public-only.

**Acceptance Scenarios**:

1. **Given** an existing configuration that omits `ignore_filename_patterns`, **When** upgraded and scanned, **Then** security findings are unchanged, non-candidate files (certificates, unsupported keystores not matching `filename_patterns`) remain absent from results, and overlap candidates such as `*.pub` sidecars are skipped entirely rather than read and classified (reducing `files_scanned` without creating new findings).
2. **Given** an existing configuration that omits `ignore_directories` or `ignore_filename_patterns`, **When** upgraded and scanned, **Then** the packaged defaults for each omitted key apply and pruning/filtering matches pre-migration expectations.
3. **Given** an existing configuration that already lists custom `ignore_directories` entries (partial extension lists from prior releases), **When** the configuration is loaded, **Then** the scanner emits an actionable warning that the list may be incomplete under replace semantics and recommends copying packaged defaults plus merging custom entries; the scan may still proceed using only the configured entries.

---

### Edge Cases

- A configuration file contains blank or whitespace-only ignore pattern strings: validation fails with an actionable error (consistent with other pattern arrays).
- A configuration file duplicates the same ignore pattern multiple times: duplicates are collapsed; behavior is unchanged.
- An ignore filename pattern uses glob metacharacters (for example `*.pub`): matching uses the same basename glob semantics as `filename_patterns`.
- A symbolic link points into a directory whose basename is ignored: the ignored directory is not descended (consistent with existing pruning rules).
- A file inside a non-ignored directory matches an ignore filename pattern: the file is skipped without being read for key assessment and is not counted in `files_scanned`.
- A file matches both `filename_patterns` and `ignore_filename_patterns` (for example `id_rsa.pub` with defaults `id_*` and `*.pub`): the ignore rule wins; the file is not read and is not counted in `files_scanned`.
- An operator removes a default ignore pattern from their configuration copy: that pattern is no longer skipped on subsequent runs (the explicit list is authoritative under replace semantics).
- An operator sets `ignore_directories = ["vendor"]` without copying packaged defaults: only `vendor` is pruned; all other default ignores are not applied until the operator copies and edits the full packaged list.
- A legacy configuration contains a partial `ignore_directories` extension list from a prior release: at load time the scanner warns that pruning may be incomplete; only the configured names are pruned until the operator copies packaged defaults and merges custom entries.
- A workspace contains package install trees or cache directories (for example `vendor/`, `.npm/`, `node_modules/`): with packaged defaults applied, those directories are pruned and package/cache artifact files matching default ignore filename patterns are skipped.
- Very large custom ignore lists: scan startup remains responsive; invalid entries are caught at load time, not mid-walk.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define all default directory ignore patterns in the packaged example configuration under `ignore_directories`, with comments explaining each category (VCS, dependencies, build output, caches, package install trees, IDE metadata, temporary directories). Package and cache directory examples include entries such as `node_modules`, `vendor`, `.npm`, `.yarn`, `.pnpm-store`, `.cache`, `.turbo`, and `.gradle` alongside existing VCS/build/cache defaults.
- **FR-002**: The system MUST introduce `ignore_filename_patterns` in the `[scan]` configuration table and define all default file ignore patterns there in the packaged example configuration, covering: (1) public-only artifacts, (2) certificate-only outputs, (3) unsupported keystore filenames, (4) cache artifact files, and (5) package-manager artifact files. File examples include `*.pub`, `authorized_keys`, `known_hosts`, `*.crt`, `*.p12`, `*.whl`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, and common cache suffixes such as `*.cache`.
- **FR-003**: Shipped default ignore patterns MUST live only in packaged configuration content (the example configuration resource), not as a hidden built-in list that operators cannot see or edit without modifying the tool itself.
- **FR-004**: When a user's configuration omits `ignore_directories` or `ignore_filename_patterns`, the system MUST apply the packaged default list for that key so scan behavior matches pre-migration expectations.
- **FR-005**: When a user explicitly sets `ignore_directories` or `ignore_filename_patterns` to an empty array, the system MUST apply no defaults for that key (disabling all ignores of that type for that run).
- **FR-006**: When a user provides non-empty entries in `ignore_directories` or `ignore_filename_patterns`, the system MUST use only the user's entries for that key (replace semantics). Packaged defaults MUST NOT be merged into an explicit non-empty list. Operators who want defaults plus custom entries MUST copy the packaged default list into their configuration and edit that copy.
- **FR-007**: Directory ignore matching MUST continue to use exact basename comparison during tree walks (promotion discovery and candidate enumeration).
- **FR-008**: Filename ignore matching MUST use basename glob semantics consistent with `filename_patterns`, MUST be evaluated before inclusion matching is acted upon, and MUST cause matching files to be skipped entirely (not read and not counted in `files_scanned`), including when the file also matches a `filename_patterns` entry.
- **FR-009**: Ignore rules MUST take precedence over inclusion rules: `ignore_directories` over `directory_names`, and `ignore_filename_patterns` over `filename_patterns`.
- **FR-010**: All ignore configuration keys MUST follow the same validation rules as other optional pattern arrays (array of non-blank strings, trimmed, actionable errors on invalid input).
- **FR-011**: Documentation shipped with the tool (example configuration header comments and operator-facing README sections) MUST be updated to describe the new keys, default contents, replace/omit/empty-list semantics, precedence rules, and migration guidance for legacy partial extension lists.
- **FR-012**: When a loaded `ignore_directories` list appears to be a partial legacy extension (significantly smaller than the packaged default catalog and missing well-known default entries), the system MUST emit an actionable warning before the scan proceeds, explaining replace semantics and recommending that the operator copy packaged defaults and merge custom entries. The warning MUST NOT block execution.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI entrypoints, application services, domain logic, and infrastructure concerns, and MUST comply with SOLID, Clean Code, DRY, and KISS.
- **NFR-002**: Feature MUST describe required unit tests that validate configuration loading, ignore-over-inclusion precedence for overlapping filename patterns, empty-list semantics, replace semantics for explicit non-empty ignore lists, and discovery pruning/filtering; any needed integration tests for representative workspaces; and the expected coverage-report impact. After implementation the full unit-test suite and coverage report are run, with any failing test triaged (test logic vs. implementation logic) before the test or code is changed.
- **NFR-003**: Feature MUST remain compliant with the project's linting, formatting, and static analysis gates.
- **NFR-004**: Feature MUST update the packaged example configuration and operator documentation; standalone packaging entry points and release artifacts do not change, but the resource file bundled inside the package does.

### Key Entities *(include if feature involves data)*

- **Directory Ignore Pattern**: A basename string identifying directories the scanner must never descend into during discovery. Applied uniformly to promotion and candidate walks. Carried in `ignore_directories`.
- **Filename Ignore Pattern**: A glob pattern matched against file basenames to skip evaluation even when inclusion patterns would match. Carried in `ignore_filename_patterns`.
- **Packaged Default Ignore Catalog**: The authoritative shipped list of directory and filename ignore patterns in the example configuration resource, used when a user's configuration omits the corresponding key.
- **Effective Ignore Set**: The active ignore patterns for a single scan run, resolved as: packaged defaults when the key is omitted, an empty set when the key is `[]`, or exactly the user's non-empty list when the key is present with entries (replace semantics).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can enumerate 100% of default directory and file ignore patterns by reading only the packaged example configuration and their own configuration file—without consulting source code.
- **SC-002**: For the repository's existing representative integration fixtures, post-migration scans produce the same security findings when using unchanged user configurations; `files_scanned` MAY decrease when packaged `ignore_filename_patterns` skip overlap candidates that were previously read and classified as non-findings.
- **SC-003**: Adding a custom ignore pattern through configuration and re-running the scan changes skip behavior on the next run without reinstalling or rebuilding the tool.
- **SC-004**: Supplying an empty ignore array and re-running the scan demonstrably includes previously skipped directories or files in discovery (verified in at least one integration scenario per ignore type).
- **SC-005**: Configuration validation rejects invalid ignore entries (blank strings, wrong types) before any filesystem walk begins, with an error message that identifies the offending key and index.
- **SC-006**: When a representative legacy partial `ignore_directories` configuration is loaded, the operator sees an actionable migration warning before the filesystem walk begins, and the scan still completes.

## Assumptions

- Default ignore patterns currently split between hidden built-in directory lists and documentation comments (file exclusions) will be consolidated into configuration keys. Packaged defaults expand to include cache and package-manager files and directories in addition to the minimal public/certificate/keystore families, further reducing noise on typical developer machines.
- Explicit non-empty ignore lists use replace semantics (not additive merge). Legacy configs with partial extension lists receive a load-time warning and may need one-time migration to copy packaged defaults and re-add custom entries.
- `ignore_filename_patterns` is a new optional key; existing configurations without it continue to work via packaged defaults.
- When `ignore_filename_patterns` is active, overlapping candidates are skipped before read; content-level classification (for example public-only) applies only when ignores are disabled via an empty array or when no ignore pattern matches.
- Automatic respect for `.gitignore` remains out of scope; explicit ignore configuration is the provided control.
- Pattern syntax and validation mirror existing `filename_patterns` / `ignore_directories` conventions for consistency.