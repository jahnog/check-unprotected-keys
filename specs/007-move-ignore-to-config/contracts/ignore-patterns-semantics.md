# Contract: Ignore Patterns in Configuration

**Feature**: 007-move-ignore-to-config  
**Related**:
- `specs/001-check-unprotected-keys/contracts/config-contract.md`
- `specs/005-search-bases-and-directory-hints/contracts/search-bases-semantics.md` (superseded
  for ignore default/additive semantics by this document)

## Purpose

Define observable loader, scope, and discovery behavior for `ignore_directories` and
`ignore_filename_patterns` after defaults move out of application code into packaged
configuration.

## Configuration Keys (under `[scan]`)

### `ignore_directories`

- **Type**: array of strings (optional).
- **Matching**: Exact basename only during `os.walk` pruning (promotion + candidate phases).
- **Precedence**: Wins over `directory_names` (unchanged).
- **Resolution**:
  - Key **omitted** → use packaged default directory list from
    `check-unprotected-keys.example.toml`.
  - Key present, **empty array** → no directory pruning.
  - Key present, **non-empty** → use exactly the configured entries (**replace**; packaged
    defaults are not merged).
- **Partial legacy warning**: When the key is explicitly present with a non-empty array that
  triggers the heuristic in `research.md`, `load_warnings` contains a migration message; scan
  still runs.

### `ignore_filename_patterns` (new)

- **Type**: array of strings (optional).
- **Matching**: Basename `fnmatch` (same rules as `filename_patterns`).
- **Precedence**: Wins over `filename_patterns`. Evaluated **before** inclusion.
- **Resolution**: Same omit / `[]` / replace rules as `ignore_directories`.
- **Effect**: Matching files are not read and are not counted in `files_scanned`.

## Packaged Defaults

Authoritative lists live only in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml`.

**Directory families** (non-exhaustive): VCS, dependencies, build output, caches, package install
trees, IDE metadata, temp dirs. Includes `vendor`, `.npm`, `.yarn`, `.pnpm-store`, `.cache`,
`.turbo`, `.gradle`, and prior defaults such as `.git`, `node_modules`, `__pycache__`.

**Filename families** (non-exhaustive):

1. Public-only (`*.pub`, `authorized_keys`, `known_hosts`)
2. Certificate-only (`*.crt`, `*.cer`, `*.csr`)
3. Unsupported keystores (`*.p12`, `*.pfx`, `*.jks`, …)
4. Cache artifacts (`*.cache`, `*.pyc`)
5. Package-manager artifacts (`package-lock.json`, `yarn.lock`, `*.whl`, …)

Structured config globs (`*.json`, `*.yaml`) are **not** in packaged defaults.

## Loader Contract

1. Parse user `.check-unprotected-keys.toml` at execution root.
2. Parse packaged example resource for default ignore catalogs (cached).
3. Resolve effective ignore lists per rules above.
4. Populate `SearchConfiguration.load_warnings` when partial-legacy heuristic fires.
5. Reject blank pattern strings with `ConfigurationError` naming key and index.

## Discovery Contract

### Directory pruning

Unchanged mechanism (`_prune_with_visit_check`); only the source of `ignore_set` changes to
resolved configuration.

### Filename filtering

In `discover_candidate_files`, for each `file_name` in a walked directory:

```text
if _match_filename_pattern(file_name, ignore_filename_patterns):
    continue  # no candidate, no files_scanned
matched = _match_filename_pattern(file_name, filename_patterns)
if matched is None:
    continue
# create CandidateFile as today
```

## Backward Compatibility

| Config shape | Directory pruning after upgrade | Filename filtering after upgrade |
|--------------|--------------------------------|----------------------------------|
| Omits both ignore keys | Packaged defaults (expanded catalog) | Packaged defaults apply |
| Omits `ignore_filename_patterns` only | Packaged dir defaults | Packaged file defaults apply |
| Partial legacy `ignore_directories` | **Only listed names** + warning | N/A |
| `ignore_filename_patterns = []` | Per dir rules | No file ignores (overlap files scanned) |

**Findings** for unchanged configs must remain identical (SC-002). **`files_scanned`** may
decrease when overlap candidates (e.g. `id_rsa.pub`) are skipped by new file ignores.

## CLI Contract

- Load warnings print to **stderr** before scan execution (one line per warning).
- Warnings do not change exit code.
- stdout remains findings-only (unchanged).

## Validation Errors (fatal)

- Non-array ignore key → `ConfigurationError`
- Blank string entry → `ConfigurationError` with index
- Packaged example resource missing or invalid → `ConfigurationError` (packaging defect)