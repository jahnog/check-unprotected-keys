# Research: Move Ignore Patterns to Configuration

## Default Catalog Source of Truth

**Decision**: Remove the `DEFAULT_IGNORE_DIRECTORIES` tuple from `config/loader.py`. Ship the
full default `ignore_directories` and `ignore_filename_patterns` lists only in
`resources/check-unprotected-keys.example.toml`. At load time, parse that packaged resource
with `importlib.resources` + `tomllib` to obtain the default catalog when a user key is
omitted.

**Rationale**:
- Satisfies FR-003 (no hidden built-in list in application code).
- Operators see the same patterns in `--print-example-config` and in repository docs.
- Single file to edit when defaults evolve.

**Alternatives considered**:
- Keep a Python constant mirroring the TOML: rejected — duplicates knowledge (DRY violation).
- Require every user config to copy the full lists: rejected — breaks omit-key ergonomics (FR-004).

## Ignore List Resolution Semantics

**Decision** (from spec clarifications):

| User config state | `ignore_directories` / `ignore_filename_patterns` effective set |
|-------------------|------------------------------------------------------------------|
| Key omitted | Packaged default list for that key |
| Key present, `[]` | Empty (no ignores of that type) |
| Key present, non-empty array | Exactly the user's entries (**replace**, no merge with packaged defaults) |

**Rationale**:
- Replace semantics make an explicit list authoritative (edge case: operator removes one default
  from a copied catalog).
- Operators who want defaults plus extras copy the packaged example block and edit it once.
- Empty array preserves the existing directory-ignore “disable all” power-user path.

**Migration impact**: Legacy configs with *partial* extension lists (old additive model) will
prune fewer directories after upgrade unless migrated. FR-012 mitigates with a load-time warning.

## Filename Ignore Evaluation Order

**Decision**: During candidate enumeration, for each file basename encountered in a walk:

1. If any `ignore_filename_patterns` entry matches (fnmatch on basename) → skip (no read, no
   `files_scanned` increment).
2. Else if any `filename_patterns` entry matches → create `CandidateFile` as today.

**Rationale**:
- Implements clarified “ignore wins on overlap” (e.g. `id_rsa.pub` with `id_*` + `*.pub`).
- Reduces I/O on public sidecars and package/cache artifacts.
- `files_scanned` may decrease vs. pre-migration overlap cases; findings unchanged (SC-002).

**Alternatives considered**:
- Evaluate inclusion first, classify public-only: rejected at clarification — conflicts with
  ignore-wins rule.
- Skip read but count in `files_scanned`: rejected — contradicts clarified acceptance criteria.

## Packaged Default Catalog Content

**Decision**: Expand defaults beyond the prior hardcoded directory tuple.

**`ignore_directories`** (basename exact match) — retain prior VCS/build/cache/IDE entries and add
package/cache install trees: `vendor`, `.npm`, `.yarn`, `.pnpm-store`, `.cache`, `.turbo`,
`.gradle` (plus existing `node_modules`, `__pycache__`, etc.).

**`ignore_filename_patterns`** (basename fnmatch) — five families:

1. Public-only: `*.pub`, `authorized_keys`, `known_hosts`
2. Certificate-only: `*.crt`, `*.cer`, `*.csr`
3. Unsupported keystores: `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `*.der`, `*.pk8`
4. Cache artifacts: `*.cache`, `*.pyc`
5. Package-manager artifacts: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.whl`,
   `*.egg`, `Cargo.lock`, `go.sum`

**Rationale**: Clarified “minimal + cache and packages” scope; keeps structured config globs
(`*.json`) out of defaults to avoid accidental suppression of unusual key filenames.

## Partial Legacy `ignore_directories` Warning

**Decision**: After resolving the effective `ignore_directories` list, if the user **explicitly**
set a non-empty `ignore_directories` in their config file and the list triggers a partial-legacy
heuristic, attach a warning string to the loaded configuration. The CLI prints warnings to
stderr after load and before the scan walk.

**Heuristic** (initial implementation):
- User explicitly provided `ignore_directories` (key present in parsed TOML).
- Entry count is strictly less than half the packaged default directory count **and**
- The list omits at least two sentinel basenames from the packaged default set (e.g. `.git` and
  `node_modules`).

**Rationale**:
- Catches the common legacy pattern `ignore_directories = ["custom-only"]` without false-positive
  warnings when an operator intentionally supplies a shorter curated list after copying and
  editing a large catalog.
- Warning is non-blocking (FR-012).

**Alternatives considered**:
- Always warn when count < packaged count: too noisy after intentional trimming.
- Fail fast: rejected — blocks CI until config edit.

**Output channel**: `SearchConfiguration.load_warnings: tuple[str, ...]` populated by loader;
`cli.main` prints each line to stderr via a small helper (consistent with operational messages,
not stdout findings).

## Layer Placement

**Decision**:

| Concern | Layer |
|---------|-------|
| Parse packaged defaults, resolve omit/empty/replace | `config/loader.py` |
| Typed fields + `load_warnings` | `config/models.py`, `domain/models.py` |
| Carry ignores on scope | `domain/scope.py` (`build_effective_scope`) |
| Prune directories (unchanged) | `adapters/filesystem.py` |
| Skip ignored filenames | `adapters/filesystem.py` (`discover_candidate_files`) |
| Print load warnings | `cli.py` (or thin helper in `adapters/reporting.py`) |

**Rationale**: Constitution layer boundaries; loader owns configuration knowledge; filesystem
adapter owns discovery filtering.

## Contract Documentation Updates

**Decision**: Add `contracts/ignore-patterns-semantics.md` as the authoritative supplement for
this feature. Update the header comment in `search-bases-semantics.md` § `ignore_directories`
defaults paragraph to reference replace semantics (pointer only — avoid editing 005 artifact
body beyond a one-line deprecation note in plan; implementers follow 007 contract).

**Rationale**: Keeps 005 artifacts stable while 007 owns the new semantics.