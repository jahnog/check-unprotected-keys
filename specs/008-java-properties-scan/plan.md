# Implementation Plan: Scan Java `.properties` Files for Unprotected Secrets

**Branch**: `008-java-properties-scan` | **Date**: 2026-06-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-java-properties-scan/spec.md`

## Summary

Add Java `.properties` files to default discovery and inspect their content for
unprotected secrets. For each property entry whose **key** matches a configurable
secret-name catalog, assess the **value**: report a plaintext credential only
when it clears a combined length-and-entropy gate; follow a value that is a path
to a key file (relative paths resolved against the `.properties` file's own
directory) and assess the referenced file via the existing key-material parser;
and — independent of the key name — report inline key material embedded in any
value. Externalized references (`${...}`, `@...@`, `#{...}`), recognized
encrypted wrappers (`ENC(...)`), and empty values are never reported. Each
offending property emits one stdout finding in `<path>#<property key>` form;
secret values never reach any output stream. Followed key files count toward
`files_scanned` exactly once, deduplicated against directly-discovered
candidates. New runtime dependency: none (`cryptography` reused).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: stdlib (`tomllib`, `importlib.resources`, `fnmatch`,
`pathlib`, `math` for entropy); `cryptography` reused for key-material assessment

**Storage**: N/A (configuration files on disk; packaged example resource in wheel)

**Testing**: `pytest` + `pytest-cov`; coverage gate ≥ 85%

**Target Platform**: Linux (POSIX); Windows supported via existing pathlib/os.walk stack

**Project Type**: CLI standalone tool (setuptools console script + PyInstaller)

**Packaging/Distribution**: Bundled resource `check-unprotected-keys.example.toml`
gains `*.properties` in `filename_patterns` and a new `property_name_patterns`
catalog; entry points unchanged (NFR-004)

**Performance Goals**: Property inspection is O(file size) per `.properties` file;
no extra directory traversal — only targeted reads of key files referenced by
FR-007, each read at most once

**Constraints**: Secret values MUST never be emitted to stdout/stderr/logs; load
and scan must stay non-interactive; stdout remains findings-only

**Quality Gates**:

- `pytest` (enforces `--cov-fail-under=85` via `pyproject.toml` addopts)
- `ruff check src/ tests/`
- `ruff format --check src/ tests/`
- `pyright src/`

**Scale/Scope**: Adds a content-inspection path alongside file-level key
classification; touches config (loader, models, example TOML), domain (new
properties module, models), adapters (new properties inspector, key_parsers
helper, reporting), the scan service, README, and tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-design gate

- **SOLID / layers**: Pure parsing + secret heuristics live in a new domain
  module (`domain/properties.py`); file/byte I/O and key-file reference following
  live in a new adapter (`adapters/properties_inspector.py`) that depends on the
  domain module and reuses `adapters/key_parsers.py`; the application service
  routes candidates and owns accounting; the CLI and reporting stay thin. The
  service depends on abstractions (parser/inspector functions), not platform
  details. ✅
- **Single Responsibility**: parsing, value classification, credential heuristic,
  key-material reuse, reference resolution, and finding emission are separate
  units. ✅
- **Open/Closed**: discovery is extended by adding `*.properties` to packaged
  `filename_patterns`; the service gains a routing branch; `KeyFinding` gains one
  optional field. No existing key-classification logic is edited. ✅
- **DRY**: inline key-material assessment and reference following reuse
  `key_parsers` via one new public helper; value placeholder/encrypted detection
  is defined once; config resolution reuses `_resolve_ignore_list`'s
  omit/empty/replace pattern. ✅
- **KISS**: secret-name matching reuses case-insensitive substring matching; the
  credential gate is a deterministic length + Shannon-entropy check with no new
  dependency; thresholds are module constants, not new config surface. ✅
- **Tests**: unit tests for parser, value classification, heuristic boundaries,
  inspector (inline key material, reference following, relative base,
  out-of-scope, missing file, dedupe), config resolution, and reporting; an
  integration test for the end-to-end workflow; existing integration
  `files_scanned` expectations updated where `*.properties` files are now scanned.
  ✅
- **Post-implementation verification**: full suite + coverage run before review;
  failures triaged (test vs. implementation) and recorded before any edit. ✅
- **Packaging**: example resource updated and shipped in the wheel; smoke
  `--print-example-config`; entry points unchanged. ✅
- **No secret leakage**: findings carry only file path + property key; values are
  never stored on findings nor printed (Principle V, NFR). ✅

No violations. Complexity Tracking table not required.

### Post-design gate

Design artifacts (`research.md`, `data-model.md`,
`contracts/properties-inspection.md`, `quickstart.md`) confirm layer placement,
the value-assessment decision order, the per-property output contract, and the
accounting rules. Re-check passed. ✅

## Project Structure

### Documentation (this feature)

```text
specs/008-java-properties-scan/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── properties-inspection.md
├── checklists/
│   └── requirements.md
└── tasks.md              # /speckit-tasks (NOT created by /speckit-plan)
```

### Source Code

```text
src/check_unprotected_keys/
├── config/
│   ├── loader.py           # Resolve property_name_patterns (omit/empty/replace + packaged default)
│   └── models.py           # ScanConfigSection: add property_name_patterns
├── domain/
│   ├── models.py           # SearchConfiguration: add property_name_patterns;
│   │                       # KeyFinding: add optional property_key; PropertyEntry + value-kind enum
│   └── properties.py       # NEW: pure parser + secret-name match + value classification + entropy gate
├── adapters/
│   ├── properties_inspector.py  # NEW: read/decode .properties, drive domain logic,
│   │                            #      follow key-file references, reuse key_parsers
│   ├── key_parsers.py      # Add public inspect_text_for_key_material(...) helper (DRY reuse)
│   └── reporting.py        # Render finding as "<path>#<property key>" when property_key set
├── services/
│   └── scan_service.py     # Route .properties candidates to inspector; per-property findings;
│   │                       # files_scanned dedupe for followed references
├── resources/
│   └── check-unprotected-keys.example.toml  # *.properties in filename_patterns + property_name_patterns catalog
└── cli.py                  # Unchanged (warnings/print already wired)

tests/
├── unit/
│   ├── test_properties_parsing.py     # NEW: separators, comments, continuations, escapes, casing
│   ├── test_property_secrets.py       # NEW: name match, value kinds, heuristic boundaries
│   ├── test_properties_inspector.py   # NEW: inline key material, ref following, scope, dedupe
│   ├── test_config_loader.py          # Extend: property_name_patterns omit/empty/replace + default
│   └── test_reporting.py              # Extend: path#key output line
└── integration/
    ├── test_properties_scan_workflow.py  # NEW: end-to-end multi-secret, externalized, ref following
    └── test_default_scan_workflow.py     # Update files_scanned where .properties now scanned
```

**Structure Decision**: Single-package CLI layout under `src/check_unprotected_keys/`
per constitution. New behavior is added as one domain module + one adapter, with
a single routing branch in the service; no layer boundary is crossed by edits.

## Implementation Tasks

### Task 1 — Packaged Configuration Surface

Add `*.properties` to `filename_patterns` and a new commented
`property_name_patterns` catalog (default: `password`, `passwd`, `pwd`, `pass`,
`secret`, `private`, `key`, `token`, `credential`, `apikey`, `passphrase`) to
`resources/check-unprotected-keys.example.toml`. Document omit/empty/replace
semantics in the header comment, matching the existing ignore-key wording.

### Task 2 — Configuration Loader & Models

Add `property_name_patterns: tuple[str, ...]` to `ScanConfigSection`
(config/models.py) and `SearchConfiguration` (domain/models.py). In
`config/loader.py`, resolve the key via the existing `_resolve_ignore_list`
omit/empty/replace helper against a packaged default parsed from the example
TOML (extend `_load_packaged_defaults` to also return the property-name catalog).

### Task 3 — Domain: Properties Parsing & Secret Heuristics (`domain/properties.py`)

Pure, I/O-free module:

- `PropertyEntry(key, value, line_number)` dataclass.
- `parse_properties(text) -> tuple[PropertyEntry, ...]` — `#`/`!` comments, blank
  lines, `=`/`:`/whitespace separators, backslash line continuations, and the
  common escape set (`\=`, `\:`, `\t`, `\n`, `\\`, leading-whitespace trim).
- `matches_secret_name(key, patterns) -> bool` — case-insensitive substring match.
- `classify_value(value) -> PropertyValueKind` — `EMPTY` / `PLACEHOLDER` /
  `ENCRYPTED` / `PATH_LIKE` / `LITERAL` (see contract for ordering).
- `is_credential_like(value) -> bool` — `len >= MIN_SECRET_LENGTH (6)` AND Shannon
  entropy `>= MIN_ENTROPY_BITS_PER_CHAR (2.5)`, rejecting pure booleans/integers.

### Task 4 — Adapter: Key-Material Reuse Helper (`adapters/key_parsers.py`)

Add `inspect_text_for_key_material(text) -> ProtectionAssessment | None` that
unescapes `\n`, encodes, and reuses `_collect_assessments` + `select_file_assessment`
to detect inline PEM/OpenSSH/PuTTY material in a property value. No duplication of
parsing logic.

### Task 5 — Adapter: Properties Inspector (`adapters/properties_inspector.py`)

`inspect_properties_file(path, *, name_patterns, scope, already_scanned)` reads
bytes (UTF-8 then Latin-1 fallback; OSError → unreadable signal), parses entries,
and for each entry applies the decision order from the contract, producing
per-property results plus the set of referenced key files actually assessed (with
their assessments) for accounting. Relative reference paths resolve against the
`.properties` file's directory; references outside `scope.canonical_root_set` or
missing are skipped gracefully. Inline key-material detection runs on every value
(cheap `-----BEGIN` pre-check) regardless of key name; name-gated heuristics apply
only to plaintext-secret and path-following cases.

### Task 6 — Service Routing & Accounting (`services/scan_service.py`)

Detect `.properties` candidates (by suffix) and route to the inspector; emit one
`KeyFinding` per offending property with `property_key` set and
`UsageCategory.EMBEDDED_CONFIG_SECRET`. Maintain a scan-level set of canonical
paths (seed from candidates) so a followed key file increments `files_scanned`
exactly once and never double-counts a directly-discovered file. Non-properties
candidates keep the existing path unchanged.

### Task 7 — Domain Model & Reporting Output

Add optional `property_key: str | None = None` to `KeyFinding` plus an
`output_line` property returning `f"{file_path}#{property_key}"` when set, else
`file_path`. Update `reporting.emit_scan_result` to print `finding.output_line`.
Generalize the `EMBEDDED_CONFIG_SECRET` remediation wording from "private key" to
"secret" so it reads correctly for plaintext credentials.

### Task 8 — Tests

Add the unit and integration suites listed in Project Structure; update
`test_default_scan_workflow.py` expectations where `*.properties` fixtures are now
scanned. Run the full suite + coverage; triage any failure (test vs.
implementation) and record the conclusion before editing.

### Task 9 — Documentation

Update `README.md` to document `.properties` inspection, the
`property_name_patterns` key (omit/empty/replace), the `<path>#<property key>`
output form, and the no-secret-values guarantee.

## Complexity Tracking

No constitution violations; this section intentionally left empty.
