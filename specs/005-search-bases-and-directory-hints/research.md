# Research: Search Bases and Directory Hints (Broad Discovery)

## Core Semantic Shift: folder_patterns → Search Bases

**Decision**: Re-document and (in new configs) rename the primary location list from `folder_patterns` to `base_folders`. The entries now represent *ancestor trees the operator authorizes the scanner to explore*, not "the exact high-signal leaf directories that contain keys."

**Rationale**:
- The original 001 design and example config explicitly chose a "curated high-signal" catalog whose goal was "minimizing the number of root directories walked."
- Real user configs (and the complaint that triggered this feature) show operators naturally want to say "look under my project / work area for anything that looks like a key by name or container."
- Treating the configured list as bases + letting the already-rich `filename_patterns` (plus embedded block parsing) do the discovery inside those bases delivers the requested "broader discovery" with almost no user maintenance.
- Directory name hints are an *additional* accelerator, not the only way breadth is achieved.

**Consequences**:
- A config containing `base_folders = ["."]` (plus sensible ignores) + the existing `filename_patterns` will now find key material at arbitrary depth.
- The "high-signal" philosophy is preserved when the operator chooses narrow bases; it is relaxed when they choose broad ones. The operator is in control.

## Directory Name Hints vs. Always Walking Bases

**Decision**: Bases are *always* included in the effective roots (subject to start-folder narrowing). Directory name hints cause *additional* promoted roots to be discovered and also enrich the `matched_folder_pattern` provenance for candidates that live under a hinted directory.

In other words:
- Full subtree filename matching under each base is the primary broad mechanism.
- Hints give you (a) guaranteed coverage of known important shapes even if their contents have non-obvious names, and (b) better metadata for usage inference (`infer_usage_category` already keys off folder names for "automation", ".ssh", etc.).

**Rationale**:
- Many real keys live in files whose names *do* match the existing broad `filename_patterns` (id_*, *.pem, *.key, privkey*, .env*, *.ovpn, *.tfvars, etc.) but sit in arbitrary subdirectories.
- Some keys sit in "secrets/" directories with less obvious filenames; hints catch those.
- Walking the base anyway means we don't have to choose between "only promoted dirs" and "everything" — we get both for the cost of one walk (or we can still optimize by walking once and noting which subtrees were hinted).

**Alternatives considered**:
- "Promoted dirs only" (no automatic base walking): rejected — it would have required users to put every possible ancestor in `directory_names` or lose recall for files in non-hinted dirs. That re-creates the maintenance problem.
- Hints as pure categorization only (no promotion): weaker than the design; we would still have had to walk everything under bases, so we might as well surface the hinted locations explicitly.

## Pruning Strategy and Default Set

**Decision**:
- Implement pruning for both the promotion name-search phase and the main candidate `os.walk`.
- Use exact basename match (simple, predictable, cheap).
- Default ignore list (shipped in the packaged example and used when the key is absent or empty):
  - VCS: `.git`, `.svn`, `.hg`
  - JS/TS & web: `node_modules`, `bower_components`, `.yarn`
  - Python: `.venv`, `venv`, `.env` (the dir, not the files), `env`
  - Build / dist: `target`, `dist`, `build`, `out`, `cmake-build-*`
  - Caches: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `coverage`, `.cache`
  - IDE: `.idea`, `.vscode`, `.vs`
  - Misc common: `tmp`, `temp`, `.tmp`
- User `ignore_directories` in the config is additive to (or replaces, per documented policy) the defaults. Exact match only.

**Rationale**:
- Real broad-base usage (".", work trees, monorepos) is otherwise dominated by noise directories that contain no keys and would generate huge numbers of uninteresting MALFORMED or unreadable reports.
- Basename-only keeps the mental model simple for operators ("anything named `node_modules` is ignored no matter where it appears").
- Having the defaults in the *example config* (and therefore in a user's local `.check-unprotected-keys.toml` after they run `--print-example-config`) makes them visible and easy to customize.

**Trade-off accepted**:
- A directory that a user *does* want to scan but that happens to be named `dist` or `build` will be ignored unless they remove it from their ignore list. This is documented and considered acceptable (they can always add an explicit narrower base that points inside the ignored tree if they really need it).

## Promotion Discovery Implementation Approach

**Decision** (for the implementation phase):
- After base expansion + start-folder narrowing, perform a single top-down `os.walk` (or a set of `glob.glob(base / "**/<name>", recursive=True)` calls) under each active base.
- During the walk, consult the current `directory_names` set and the active ignore set.
- Collect promoted directories.
- Union with the bases themselves.
- Then hand the combined set to the existing `discover_candidate_files` (or perform the candidate collection in the same pass for efficiency, enriching the matched label).

Using the same walk for promotion and candidate collection is attractive for performance (one traversal of the allowed trees) and for building rich per-candidate provenance.

`on_error` handling for promotion should feed into the existing `DiscoveryIssue` collection so that unreadable areas during promotion are reported consistently with walk errors today.

## Interaction with --start-folder

**Decision**:
- `resolve_start_folder` validation is unchanged (early, before config load).
- The resolved (or None) start folder is passed into the new scope resolver.
- Narrowing logic (`narrow_root_directories` and friends) is extended / reused so that:
  - Only bases that are at or under (or contain) the start folder participate.
  - Promotion search is performed only under the intersection of the participating bases and the start folder.
- The "start folder replaces a parent root" behavior from spec 004 continues to work when a configured base is an ancestor of the supplied start folder.

This keeps the mental model "start-folder narrows the configured folder matches" while the "configured folder matches" are now the combination of bases + auto-promoted hints.

## Matched Folder Pattern Provenance

**Decision**:
- Keep the field as `str` (no new dataclass or breaking change for this feature).
- Evolve the *value* stored to something like:
  - For a file reached because of a base: `"base:."` or `"base:repos/myproj"`
  - For a file inside a promoted dir: `"base:., hint:secrets"` or `"base:infra, hint:deploy"`
- Update `infer_usage_category` (and any tests that assert on the exact string) only where the richer value improves behavior (it already does substring checks for ".ssh", automation hints, etc.).
- Malformed issues continue to record the value that was current at discovery time.

This is a pure enrichment. Old narrow configs that produced absolute root paths as the label will produce similar or more informative labels.

## Backward Compatibility & Migration Strategy

**Decision**:
- The config loader will accept the legacy `folder_patterns` key when `base_folders` is absent.
- In the compat path the legacy list is used as the set of bases.
- As a user-experience nicety, any simple bare names (no `/` or glob chars) present in the legacy list are also contributed to the effective directory hints for that run. This means many existing "I listed a bunch of common dir names" configs will automatically get broader discovery on upgrade.
- The packaged example config will be updated to the new key names + a good `directory_names` list + `ignore_directories`.
- Documentation (README, the header comments in the example toml, and the new spec artifacts) will contain a short "Migrating from folder_patterns" section.
- After one or two releases the compat bridge can be considered for deprecation (but is not removed in this feature).

This approach lets users who just run `--print-example-config` again get the modern shape, while old committed or copied configs keep working.

## Test Strategy

**Unit level** (new or extended):
- `tests/unit/test_scope_resolution.py` (or a new focused module if it grows too large) will contain direct tests for:
  - Base expansion (relative, absolute, ~, globs).
  - Promotion discovery (shallow + deep nesting, multiple hints, dedup).
  - Pruning (default set, user override, interaction with hints).
  - Start-folder narrowing applied to bases + promotion.
  - Compat path (legacy key → bases + auto-hints).

**Contract / Integration**:
- Existing start-folder and default-scan contract tests must continue to pass (they use narrow folder patterns today; they exercise the compat path).
- New or extended integration tests that configure a broad base + hints and assert on the set of discovered candidates (by path or count) at various depths.
- Tests that deliberately place noise directories and verify they contribute zero candidates.

**Coverage**:
- The 85% gate with branch coverage remains mandatory.
- New code paths (promotion, pruning, the three new config fields through the loader, the enriched matched label) must be exercised by the added tests.

**No change to the "test the behavior, not the implementation" spirit** for the thin CLI layer; contract tests stay the primary CLI surface validation.

## Performance & Noise Considerations

**Accepted trade-off**:
- Broad bases will increase `files_scanned` and the number of MALFORMED lines emitted on stderr for any given tree, because more files whose names match a filename pattern will be stat'ed and partially parsed.
- Pruning + the existing "only filename-matched files are even opened" rule + MALFORMED classification on stderr (never on stdout) keep the operator experience usable.
- Operators who find the noise too high can narrow their bases or extend the ignore list.

We will not add automatic `.gitignore` respect in this feature (a secret scanner often *wants* to see material that is deliberately untracked). If future operators request it we can add an opt-in.

## Removal of the Dead Duplicate Package

As part of this feature work we will delete `src/find_unencrypted_keys/` in its entirety.
- Grep across the repository shows that all references are self-contained inside that tree (old internal imports using the previous package name).
- The current `pyproject.toml` uses `packages.find` under `src`; removing the directory simply stops the old package from being packaged or importable.
- No tests, scripts, or docs outside that tree import from it.
- Cleanup is housekeeping that improves the repository while we are touching scope resolution and configuration anyway.

## Open Questions / Future Work (Explicitly Out of Scope Here)

- Should `directory_names` later support limited glob syntax (e.g. `*-secrets`) or stay exact basenames only? (Start with exact.)
- Should there be a "promotion only" mode that skips walking non-hinted parts of bases? (Current design always includes bases for maximum recall under the operator's chosen trees.)
- Automatic or suggested ignore extensions based on language/ecosystem detection.
- Time or depth budgets for very large promotion walks.
- Richer structured provenance on `CandidateFile` (a small dataclass instead of an enriched string) — can be done later without breaking the string-based consumers if we keep the string field as a rendered form.

## Summary of Key Decisions Applied

- Bases = authorized ancestor trees; full subtree filename matching under them is the main broad mechanism.
- `directory_names` = simple list for auto-promotion + better metadata.
- Pruning with good defaults is mandatory for the feature to be usable.
- Legacy `folder_patterns` treated as bases (with bonus auto-hint contribution) for compat.
- `--start-folder` narrows bases + promotion search.
- `matched_folder_pattern` is enriched in place (string) rather than introducing a new type in this increment.
- Dead duplicate package tree is removed.
- Tests follow the existing unit / contract / integration layering; new coverage targets the resolver and discovery phases.

These decisions were cross-checked against the original 001 spec input ("starting from the root folder"), the 004 start-folder work, the current data model and contracts, and the observed user config that motivated the request. The design is an evolution that makes the tool far more useful for broad discovery while preserving the operator-controlled, low-surprise character of the original scanner.