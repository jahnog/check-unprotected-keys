# Quickstart: Search Bases and Directory Hints (Broad Discovery)

**Purpose**: Provide runnable validation scenarios that prove the new search-bases + directory-hints + pruning model delivers broader discovery without `**/foo` maintenance, that legacy configs continue to work, that `--start-folder` still narrows correctly, and that the full quality gates pass.

References:
- Feature spec: [spec.md](./spec.md)
- Data model: [data-model.md](./data-model.md)
- Research & decisions: [research.md](./research.md)
- Contracts supplement: [contracts/search-bases-semantics.md](./contracts/search-bases-semantics.md)
- Primary 001 config contract: `specs/001-check-unprotected-keys/contracts/config-contract.md`

## Prerequisites

- Python 3.12+
- `uv` package manager
- A clean checkout of the repository

## Setup

```bash
uv sync --extra dev
```

This gives you the editable install plus ruff, pyright, pytest, coverage, etc.

## Validation Scenario 1: Dedicated Unit Tests for the New Resolver Logic

After the new unit tests are added to `tests/unit/test_scope_resolution.py` (and any focused promotion/pruning tests), run only the relevant slices:

```bash
uv run --extra dev pytest tests/unit/test_scope_resolution.py -q -k "base or promote or prune or directory_name or ignore or compat" --tb=line
```

Expected outcome:
- All new tests for base expansion, promotion discovery (deep + shallow), pruning (default + override), start-folder narrowing over the new model, and the legacy `folder_patterns` compat path pass.
- Coverage of `src/check_unprotected_keys/config/loader.py`, `adapters/filesystem.py`, and `domain/scope.py` increases for the exercised branches.
- No pre-existing tests in the module are broken.

## Validation Scenario 2: Broad Base + Directory Hints Discovers Material at Depth (No **/ Required)

Use (or let the test suite create) a workspace that has:

- A base root (e.g. the workspace itself or a `fixtures/broad-scope` tree).
- Key material inside hinted directories at multiple depths (`apps/api/secrets/...`, `services/bar/deploy/...`, top-level `keys/...`).
- Additional key-named files (matching `filename_patterns`) that live outside any hinted directory but still under the base.
- Some noise directories (`.git`, `node_modules`, `target`, etc.).

Then run the relevant integration test(s):

```bash
uv run --extra dev pytest tests/integration/ -q -k "broad or base or promote" --tb=line
```

Or execute a manual reproduction (after creating a minimal workspace as shown in the integration test helpers or quickstart Scenario 3 style):

```bash
# (example manual flow — the exact commands live in the integration test that exercises the new model)
uv run --extra dev python -m check_unprotected_keys   # with a .check-unprotected-keys.toml that uses base_folders + directory_names
```

Expected outcome:
- `files_scanned` is substantially higher than a narrow "only direct children of the base" config would have produced.
- Candidates (or at least evaluated files) are found both inside promoted hinted dirs *and* via plain filename matches in non-hinted locations under the base.
- No `**/ ` or complex globs appear in the user's `base_folders` or `directory_names` lists.
- `matched_folder_pattern` values on candidates (visible via debug or by inspecting malformed issues if you force some) contain base/hint provenance.
- Stdout contains only real findings; stderr contains the normal summary + any MALFORMED guidance.

## Validation Scenario 3: Pruning Prevents Descent into Noise (Default + Override)

Configure (or let the test fixture use) a broad base that also contains several well-known noise directories at various depths, some of which contain files whose names would match `filename_patterns`.

Run the broad discovery integration test with pruning assertions, or a manual invocation against a temp layout that includes `node_modules/some-package/id_rsa` (or similar) plus a real secret in `secrets/db.key`.

Expected outcome:
- Zero candidates are produced from inside any ignored directory.
- The real secret in the non-ignored hinted location *is* evaluated.
- Adding a name to the user's `ignore_directories` in the config causes that name (anywhere under the bases) to be pruned.

## Validation Scenario 4: Legacy `folder_patterns` Config Still Works (Compat + Auto-Hints)

Create a temp workspace with a `.check-unprotected-keys.toml` that uses only the old key name:

```toml
[scan]
folder_patterns = [
  "fixtures",
  "secrets",
  "deploy"
]
filename_patterns = ["id_*", "*.pem", ".env*"]
```

Run the scanner (or the config contract test) against a layout that has material under those names at depth.

Expected outcome:
- The config loads without error (no "unknown key" or "must define base_folders").
- The scan runs and, thanks to the auto-contribution of bare names to hints, discovers material under the named directories even when they are not direct children of the base.
- The same layout with an explicit migrated `base_folders` + `directory_names` config produces equivalent or better results.

Re-run the full config contract test module to be sure:

```bash
uv run --extra dev pytest tests/contract/test_config_contract.py -q --tb=no
```

## Validation Scenario 5: --start-folder Still Narrows Bases + Promotion

Use an existing start-folder contract test or the new broad + start-folder integration scenario:

```bash
uv run --extra dev pytest tests/contract/test_cli_start_folder_contract.py -q --tb=line
uv run --extra dev pytest tests/integration/test_start_folder_scan.py -q --tb=line
```

Also run a scenario (manual or test) that supplies `--start-folder` pointing at a subtree that contains only *some* of the hinted material under a broad base.

Expected outcome:
- Only candidates under the supplied start folder are reported.
- `files_scanned` and the set of promoted roots are smaller (or equal) compared with the same config without `--start-folder`.
- Filename patterns are unchanged.
- The classic "narrow to a subtree" and "replace parent root" behaviors from spec 004 continue to hold.

## Validation Scenario 6: Full Quality Gate Run

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pyright .
uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85 -q
```

Expected outcome: all gates green. New tests for the 005 paths contribute positively to coverage. No regressions in the 001–004 paths.

## Notes

- The quickstart deliberately re-uses the heavy lifting in `tests/support/fixture_builders.py` and the pre-existing contract/integration tests (especially everything that exercises narrow `folder_patterns` and `--start-folder`).
- New manual workspace setup is shown only for quick local verification of broad discovery and pruning; the authoritative proofs are the automated tests.
- Because the feature changes the *location* model while preserving the rest of the pipeline, the most important runnable proofs are:
  1. The new unit tests for the resolver (Scenario 1).
  2. At least one integration scenario that demonstrates discovery at depth with a broad base + hints and no `**/` (Scenario 2).
  3. Pruning verification (Scenario 3).
  4. Legacy compat (Scenario 4).
  5. Unchanged start-folder behavior (Scenario 5).
  6. The full gate run (Scenario 6).

After executing the scenarios above, the implementation satisfies the acceptance criteria in the feature spec (SC-001 through SC-008), the contracts supplement, and the project's constitution / coverage requirements. The dead duplicate package cleanup can be verified as part of the final polish by confirming the directory is gone and a full grep finds no references.