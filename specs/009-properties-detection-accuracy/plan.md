# Implementation Plan: Precise `.properties` Secret Detection (Near-Zero False Positives, Zero False Negatives)

**Branch**: `feature/properties-detection-accuracy` | **Date**: 2026-06-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-properties-detection-accuracy/spec.md`

## Summary

Replace the 008 single loose detection gate — substring key matching plus
`len>=6 ∧ entropy>=2.5` — with a **layered, confidence-tiered classifier** in the
existing pure properties domain module. Five mechanisms work together: (1)
token-aware key matching kills container-word false matches (`compass`, `monkey`,
`tokenizer`); (2) key-name strength tiers (STRONG/WEAK/NONE) with qualifier
demotion calibrate how much value evidence is required; (3) an unconditional
value-signature layer (provider tokens, JWT, embedded-credential URLs,
high-entropy blobs) catches secrets under benign key names and anchors recall;
(4) conservative, tier-aware value-shape and sample/mask exclusions remove the
benign-config false positives (`localhost`, `RS256`, `order.created.event`,
`changeme`); (5) expanded externalization/encryption recognition plus
hardcoded-placeholder-default assessment. A labeled accuracy corpus with enforced
recall/false-positive thresholds makes the guarantee regression-proof. No new
runtime dependency; output format, accounting, scope/ignore rules, and parsing
are carried over from 008 unchanged.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: stdlib (`re`, `math`, `enum`, `dataclasses`,
`pathlib`); `cryptography` reused for key-material assessment. No new dependency.

**Storage**: N/A (config + packaged example resource; labeled corpus as a Python
fixture module).

**Testing**: `pytest` + `pytest-cov`; coverage gate ≥ 85% (enforced via
`pyproject.toml` addopts `--cov-fail-under=85`).

**Target Platform**: Linux/POSIX; Windows via the existing pathlib/os.walk stack.

**Project Type**: CLI standalone tool (setuptools console script + PyInstaller).

**Packaging/Distribution**: Bundled `check-unprotected-keys.example.toml` comment
updated (token-aware semantics, tiering, value signatures, the optional
`property_value_ignore` key). Entry points unchanged; no new dependency (NFR-004).

**Performance Goals**: O(file size) per `.properties` file; signature/shape regex
work is bounded per value and applied only to candidate values; no extra
directory traversal beyond 008's targeted reference reads (SC-005).

**Constraints**: Secret values MUST never reach stdout/stderr/logs; load and scan
stay non-interactive; stdout remains findings-only in `<path>#<key>` form.

**Quality Gates**:

- `pytest` (enforces `--cov-fail-under=85`)
- `ruff check src/ tests/`
- `ruff format --check src/ tests/`
- `pyright src/`

**Scale/Scope**: Refactors the value/name heuristics inside one domain module and
rewrites one adapter function; small additive changes to `key_parsers`, config
models/loader, the example TOML, reporting wording, and the test suite (new unit
suites + a labeled accuracy corpus). The service routing and the output/accounting
paths are untouched.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-design gate

- **SOLID / layers**: All new detection logic (tokenization, tiering, signatures,
  shape/sample exclusions, widened placeholder/encrypted recognition,
  defaulted-default extraction, tiered gate) is pure and lives in
  `domain/properties.py`. The adapter (`properties_inspector.py`) only orchestrates
  the new pure functions and reuses `key_parsers`; the service and reporting stay
  thin. High-level logic depends on abstractions (pure functions), not platform
  details. ✅
- **Single Responsibility**: tokenization, tier classification, value-signature
  detection, sample/shape exclusion, placeholder handling, the credential gate,
  and key-material reuse are each separate functions with one reason to change. ✅
- **Open/Closed**: the value-signature catalog, qualifier denylist, sample
  vocabulary, and shape predicates are curated constants extended by addition; the
  inspector gains one new branch ordering; file-level key classification is
  untouched (only a `CERTIFICATE → PUBLIC_ONLY` branch is added to `key_parsers`,
  additive). ✅
- **DRY**: certificate handling reuses the existing `PUBLIC_ONLY` path rather than
  a parallel value rule; the optional `property_value_ignore` reuses
  `_resolve_ignore_list`; placeholder-default assessment re-enters the same
  decision functions instead of duplicating them. ✅
- **KISS**: tiers/thresholds/catalogs are deterministic module constants (one
  source of truth), not new config surface; the only added config key is one
  optional ignore list. No new dependency, no ML, no scoring model. ✅
- **Tests**: unit tests for tokenization/tiering, signatures, shape/sample
  exclusions, widened placeholder/encrypted recognition, defaulted-default
  assessment, and the tiered gate; a labeled accuracy corpus enforcing recall/FP
  thresholds; an integration test (benign file → zero findings; embedded-cred URL
  + literal secret → reported). Existing 008 tests that encode the old loose
  behavior are updated with NFR-002 triage recorded. Coverage ≥ 85%. ✅
- **Post-implementation verification**: full suite + coverage run before review;
  failures triaged (test vs. implementation) and recorded before any edit. ✅
- **Packaging**: example resource comment updated and shipped; smoke
  `--print-example-config`; entry points unchanged; no new dependency. ✅
- **No secret leakage**: findings carry only path + property key; the accuracy
  corpus asserts booleans only; no value is stored or printed (Principle V, NFR). ✅
- **Git Flow**: implementation proceeds on `feature/properties-detection-accuracy`
  created via `git flow feature start` just before coding; all commits/PR are
  manual (Principle VI). ✅

No violations. Complexity Tracking table not required.

### Post-design gate

Design artifacts (`research.md`, `data-model.md`,
`contracts/properties-detection.md`, `quickstart.md`) confirm the layer placement
(pure domain + thin adapter), the per-entry decision order, the tier/signature
rules, the unchanged output/accounting contract, and the enforced-accuracy
corpus. Re-check passed. ✅

## Project Structure

### Documentation (this feature)

```text
specs/009-properties-detection-accuracy/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── properties-detection.md
├── checklists/
│   └── requirements.md
└── tasks.md              # /speckit-tasks (NOT created by /speckit-plan)
```

### Source Code

```text
src/check_unprotected_keys/
├── domain/
│   ├── properties.py     # MAJOR: tokenize_key, classify_key_tier (KeyNameTier),
│   │                     #   match_value_signature (ValueSignature),
│   │                     #   is_sample_placeholder, is_non_secret_shape,
│   │                     #   placeholder_default, tier-aware is_credential_like,
│   │                     #   widened PLACEHOLDER/ENCRYPTED in classify_value;
│   │                     #   new constants; remove old matches_secret_name
│   └── models.py         # SearchConfiguration: add property_value_ignore
├── adapters/
│   ├── properties_inspector.py  # Rewrite _assess_entry to the new decision order;
│   │                            #   add VALUE_SIGNATURE origin; assess placeholder
│   │                            #   defaults; thread value_ignore
│   ├── key_parsers.py    # Add CERTIFICATE → PUBLIC_ONLY branch in _inspect_key_blob
│   └── reporting.py      # (If needed) generalize embedded-config-secret wording
├── config/
│   ├── models.py         # ScanConfigSection: add property_value_ignore
│   └── loader.py         # Resolve property_value_ignore via _resolve_ignore_list
├── services/
│   └── scan_service.py   # Thread value_ignore to the inspector; routing unchanged
├── resources/
│   └── check-unprotected-keys.example.toml  # Update property_name_patterns comment;
│                                            #   document token-aware/tiering/signatures
│                                            #   + optional property_value_ignore
└── cli.py                # Unchanged

tests/
├── fixtures/
│   └── properties_corpus/
│       └── corpus.py                     # NEW: MUST_FLAG / MUST_NOT_FLAG labeled cases
├── unit/
│   ├── test_property_secrets.py          # Extend/UPDATE: tokenization, tiering,
│   │                                     #   shapes, sample vocab, placeholder kinds,
│   │                                     #   defaulted default, tiered gate (triage old cases)
│   ├── test_value_signatures.py          # NEW: signature catalog (positive/negative)
│   ├── test_properties_inspector.py      # UPDATE: new decision order, VALUE_SIGNATURE,
│   │                                     #   cert non-finding, placeholder default
│   ├── test_properties_accuracy.py       # NEW: corpus recall/FP-rate thresholds
│   ├── test_key_parsers.py               # Extend: CERTIFICATE → PUBLIC_ONLY
│   └── test_config_loader.py             # Extend: property_value_ignore omit/empty/replace
└── integration/
    └── test_properties_scan_workflow.py  # UPDATE: benign file → 0 findings;
                                          #   embedded-cred URL + literal secret reported
```

**Structure Decision**: Single-package CLI layout under
`src/check_unprotected_keys/` per constitution. The change is concentrated in one
pure domain module plus one adapter function; all other edits are small and
additive, and no layer boundary is crossed.

## Implementation Tasks

### Task 1 — Domain: token-aware matching & tiers (`domain/properties.py`)

Add `tokenize_key`, `KeyNameTier`, and `classify_key_tier` (substring-safe +
token-exact catalogs, qualifier denylist, STRONG/WEAK/NONE per research
Decision 1–2). Remove `matches_secret_name`.

### Task 2 — Domain: value-signature layer (`domain/properties.py`)

Add `ValueSignature` and `match_value_signature` with the curated, anchored,
length-bounded catalog (research Decision 3), including the embedded-credential
URL rule (non-placeholder `pw` group) and the high-entropy-blob rule.

### Task 3 — Domain: exclusions, placeholders, tiered gate (`domain/properties.py`)

Add `is_sample_placeholder` (Decision 5), `is_non_secret_shape` (tier-aware,
Decision 6), `placeholder_default` and widened `classify_value`
PLACEHOLDER/ENCRYPTED recognition (Decision 7), and make `is_credential_like`
tier-aware (STRONG base / WEAK strict, Decision 4). Add all new constants.

### Task 4 — Adapter: certificate handling (`adapters/key_parsers.py`)

Add a `-----BEGIN CERTIFICATE-----` branch in `_inspect_key_blob` returning
`PUBLIC_ONLY` (FR-010, DRY with existing public-key handling).

### Task 5 — Adapter: rewrite the decision order (`adapters/properties_inspector.py`)

Rewrite `_assess_entry` to the §3 decision order: inline material → value
signature → value kind (with placeholder-default re-assessment) → key tier →
path-like follow → literal sample/shape exclusions → tiered gate. Add
`VALUE_SIGNATURE` to `PropertyFindingOrigin`. Thread a `value_ignore` parameter
through `inspect_properties_file`.

### Task 6 — Config: optional value-ignore list

Add `property_value_ignore` to `ScanConfigSection` (config/models.py) and
`SearchConfiguration` (domain/models.py); resolve it in `config/loader.py` via
`_resolve_ignore_list` (default empty). Thread it from `scan_service.py` to the
inspector. Routing/accounting unchanged.

### Task 7 — Packaged config & docs

Update the `property_name_patterns` comment block in the example TOML to describe
token-aware matching, tiering, the unconditional value-signature layer, and the
optional `property_value_ignore` key. Update `README.md` accordingly.

### Task 8 — Labeled corpus & accuracy test

Add `tests/fixtures/properties_corpus/corpus.py` (MUST_FLAG / MUST_NOT_FLAG) and
`tests/unit/test_properties_accuracy.py` asserting recall == 100% on MUST-FLAG and
FP-rate ≤ target on MUST-NOT-FLAG (FR-014).

### Task 9 — Unit & integration tests + triage

Add `test_value_signatures.py`; extend `test_property_secrets.py`,
`test_properties_inspector.py`, `test_key_parsers.py`, `test_config_loader.py`,
and the integration workflow. Update any 008 test that encodes the old loose
behavior (substring matches, `is_credential_like("localhost") is True`), recording
the test-vs-implementation triage per NFR-002 before editing. Run the full suite +
coverage; triage any failure before changing test or code.

## Complexity Tracking

No constitution violations; this section intentionally left empty.
