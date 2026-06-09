# Implementation Plan: Search Bases and Directory Hints (Broad Discovery)

**Branch**: `[005-search-bases-and-directory-hints]` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-search-bases-and-directory-hints/spec.md`

## Summary

Implement the "Search Bases + Directory Name Hints + Pruning" alternative design for broader discovery.

The change is primarily in configuration semantics and the scope-resolution / discovery phase:

- Evolve `folder_patterns` → `base_folders` (with legacy compat) in the TOML schema, loader, and models.
- Add `directory_names` (for automatic promotion of common secret-holding subdirectories under bases) and `ignore_directories` (with good defaults) to `SearchConfiguration`.
- Extend `resolve_effective_scope` (and add a promotion helper) in `adapters/filesystem.py` so that effective roots become the union of resolved bases and promoted directories, subject to pruning and `--start-folder` narrowing.
- Enrich the `matched_folder_pattern` label on `CandidateFile` (and malformed issues) with base/hint provenance while keeping it a string.
- Reuse / lightly extend the existing `narrow_root_directories` logic for the start-folder interaction over the new model.
- Update the packaged example config, loader validation, data model, contracts, and all documentation.
- Add unit, contract, and integration coverage for the new resolution paths, promotion, pruning, start-folder interaction, and compat path.
- As housekeeping, delete the dead `src/find_unencrypted_keys/` tree (old package name; all references were internal).

No changes to the core key-parsing, classification, `ScanResult`, reporting shape, CLI surface (beyond what the config now supports), or packaging are required. The "Checked N / findings on stdout only" contract and the 85% coverage gate remain in force.

## Technical Context

**Language/Version**: Python 3.12 (project `requires-python = ">=3.12"`).

**Primary Dependencies**: Only `cryptography` at runtime (unchanged). Dev tooling (pytest, pytest-cov, ruff, pyright, etc.) is already declared under `[project.optional-dependencies] dev`.

**Storage / I/O**: Transient only. All new work is path resolution + `os.walk` / glob under user-authorized bases. No new persistent state.

**Testing**: `pytest` with branch coverage, `--cov-fail-under=85`. Existing tests in `tests/unit/`, `tests/contract/`, `tests/integration/`, and support fixtures in `tests/support/fixture_builders.py`. Many current tests deliberately pass narrow `folder_patterns` values (e.g. `"fixtures/default-scope"`) — these will continue to work via the compat path and will also serve as regression coverage for narrow usage.

**Target Platform**: OS-independent (portable `pathlib` + `os`). Primary CI on Linux; the PyInstaller standalone and wheel must keep working on common developer platforms.

**Project Type**: Standalone CLI security scanner (console script + optional one-file executable).

**Packaging**: `packages.find` under `src` in pyproject.toml. Removing `src/find_unencrypted_keys/` is sufficient; no entry-point or package-data changes.

**Performance Goals**: Promotion discovery + a pruned walk under a modest number of bases (including ".") must be practical on developer machines and small-to-medium monorepos. One traversal that both promotes and collects candidates is preferred for efficiency.

**Quality Gates** (exact commands, local and CI):
`uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pyright . && uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85`

Release validation also runs the smoke test script and `python -m build`.

**Constraints**:
- `resolve_start_folder` validation remains early (before config load) — unchanged from spec 004.
- `--start-folder` narrows bases + promotion but never touches `filename_patterns`.
- Legacy `folder_patterns` key must be accepted (compat) so existing user configs do not hard-fail.
- All error paths and summaries must remain secret-safe.
- `followlinks=False` and existing error collection on walk must be preserved.
- The stdout-only-for-real-findings contract is sacred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Design Gate**: PASS (initial)

- Clear separation of concerns is maintained: config loading (config/), scope resolution & filesystem discovery (adapters/filesystem.py + domain/scope.py), service orchestration, classification, and reporting.
- Public seams (`SearchConfiguration`, `EffectiveScope`, `ScanRequest`, `CandidateFile`) are evolved in a backward-compatible way for existing narrow usage.
- Unit tests for the new/changed behavior (base expansion, promotion, pruning, enriched labels, start-folder narrowing over the new model, compat) are explicitly required by the spec (NFR-002, SC-006) and will be added.
- Linting / formatting / static / coverage gates are documented exactly and match pyproject.toml.
- Standalone packaging impact is "none" (the dead duplicate removal is pure cleanup; the new feature adds no entry points).

**Post-Design Review**: (to be filled after research.md, data-model.md, contracts are complete)

- [research.md](./research.md) will record the decisions on bases-vs-hints, pruning defaults, compat strategy, start-folder interaction, test placement, performance/noise trade-offs, and removal of the duplicate package.
- [data-model.md](./data-model.md) will clearly define the evolved `SearchConfiguration`, the new promotion & pruning concepts, the resulting `EffectiveScope`, and the (string) enrichment of `matched_folder_pattern`.
- Contracts will be supplemented (focused search-bases semantics + reference to the 001 config contract) without duplication.
- Quickstart will give concrete, repeatable commands that exercise unit tests for the resolver, broad-base + hint scenarios, pruning, start-folder narrowing, and the full quality gates.
- All artifacts will respect the existing layered architecture and the "test behavior at the right seam" practice (heavy use of existing contract/integration tests for end-to-end + focused unit tests for the new resolution logic).

## Project Structure

### Documentation (this feature)

```text
specs/005-search-bases-and-directory-hints/
├── spec.md
├── data-model.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── contracts/
    └── search-bases-semantics.md   (or config-contract-supplement.md)
```

### Source Code (changes expected)

```text
src/
└── check_unprotected_keys/
    ├── config/
    │   ├── models.py          # extend ScanConfigSection + SearchConfiguration with the three new fields
    │   └── loader.py          # accept legacy folder_patterns, validate + populate new fields, update example text helper if needed
    ├── adapters/
    │   └── filesystem.py      # resolve_effective_scope becomes the orchestrator; new/expanded promotion + pruning helpers; enrich matched_folder_pattern during discovery
    ├── domain/
    │   ├── models.py          # (minor) EffectiveScope may grow optional provenance fields; SearchConfiguration is imported from config
    │   └── scope.py           # extend narrow_root_directories / build_effective_scope for the new model if the logic doesn't fit cleanly in adapters
    ├── resources/
    │   └── check-unprotected-keys.example.toml   # major update: new keys, good directory_names list, ignore_directories with comments
    └── (no changes required in cli.py, services/, key_parsers/, reporting.py for core behavior)
```

### Tests (additions / extensions)

```text
tests/
├── unit/
│   └── test_scope_resolution.py          # (primary) new tests for base expansion, promotion, pruning, start-folder narrowing, compat, enriched labels
├── contract/
│   └── test_config_contract.py           # may need light updates for the new keys + legacy acceptance
├── integration/
│   └── test_default_scan_workflow.py     # (or new file) broad-base + hint scenarios that assert on discovered candidate counts / locations at depth
├── support/
│   └── fixture_builders.py               # likely small additions: helpers to create workspaces with deep hinted dirs + noise dirs for pruning tests
└── (existing start-folder and default-scan tests continue to provide strong regression coverage via the compat path)
```

**Cleanup**:
- Delete entire `src/find_unencrypted_keys/` tree (confirmed to have only self-referential imports).

## Complexity Tracking

No constitutional violations or approved complexity exceptions are required.

The work touches configuration loading, the scope-resolution adapter (the natural seam for "where do we look?"), and documentation/tests. It is a medium-sized feature for this codebase because it changes the mental model of the primary configuration axis while preserving all existing observable contracts for narrow usage and for `--start-folder`.

The removal of the dead duplicate package is pure cleanup with zero behavior impact.

## Dependencies on Prior Specs

- 001 (core scanner, data model, contracts)
- 004 (start-folder validation + narrowing) — the new model must not regress any of the four states or the narrowing behavior
- The "high-signal" philosophy and example config commentary from the README and 001-era docs will be updated to reflect the new controllable-breadth model.

## Risks & Mitigations

- **Risk**: Existing users with many bare names in `folder_patterns` see suddenly much larger scans.  
  **Mitigation**: Strong defaults for `ignore_directories`, clear migration guidance in the example header and README, compat path that still works, and the fact that operators choose their bases.

- **Risk**: Promotion or broad walking is slow on huge trees.  
  **Mitigation**: Pruning is applied early in both phases; one combined walk is preferred; docs will note that very large bases should be paired with good ignores or narrower bases.

- **Risk**: `matched_folder_pattern` string changes break downstream string assertions in tests.  
  **Mitigation**: Update the affected tests as part of the feature; the field was already treated as "the label that reached this file" rather than a machine-readable token in most places.

## Open Questions for Implementation Phase

(See research.md for the decisions already made. Any remaining tactical choices — e.g. exact shape of the enriched label string, whether promotion and candidate collection share a single walk, exact additive vs. replace semantics for user ignore_directories — will be recorded in research.md or as small code-review notes.)

## Next Steps After This Plan

1. Complete research.md, data-model.md, quickstart.md, checklists/requirements.md, and the contracts supplement.
2. Produce tasks.md (detailed, story-grouped, with checkpoints).
3. Implement in small increments:
   - Config model + loader + updated example (with compat).
   - Promotion + pruning helpers + updated resolve_effective_scope.
   - Enrichment of matched labels + any necessary updates to infer_usage_category / malformed recording.
   - Unit tests (the bulk of new test code).
   - Integration / contract additions or adjustments.
   - Docs (README, example header, cross-references).
   - Delete the dead tree.
4. Run full gates + quickstart scenarios at each checkpoint.
5. Commit with clear messages referencing the user stories / spec sections.