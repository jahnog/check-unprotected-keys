# Implementation Plan: Expand Secret Patterns

**Branch**: `[002-expand-secret-patterns]` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-expand-secret-patterns/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Expand the shipped TOML folder and filename pattern catalog to cover curated,
Linux-first user-home and repo-local conventions that commonly hold supported
private-key material, including supported key blocks embedded in matched text
containers, while preserving the current CLI contract, scan-service flow,
classification engine, packaging workflow, and start-folder semantics.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `cryptography` for PEM/OpenSSH key parsing and
classification; Python standard library modules `argparse`, `pathlib`, `glob`,
`fnmatch`, and `tomllib`; `PyInstaller` for standalone release artifact builds

**Storage**: N/A; read-only local filesystem plus root-level
`.check-unprotected-keys.toml` and `.check-unprotected-keys.toml.example`
configuration files

**Testing**: `pytest`, `pytest-cov`, fixture-based unit tests, integration
tests, and contract checks for CLI and configuration behavior

**Target Platform**: Linux x86_64 local filesystems first, with `Path.expanduser`
support for curated user-home patterns and portable path handling for later
cross-platform support

**Project Type**: Standalone CLI security scanner

**Packaging/Distribution**: `setuptools` console script for development and
wheel builds, plus a `PyInstaller` standalone executable smoke-tested during
release validation

**Performance Goals**: Maintain the existing target of scanning 5,000 candidate
files within 2 minutes on commodity SSD-backed hardware while streaming
line-oriented findings, even after the default pattern catalog expands

**Constraints**: Local filesystem only, no secret material in logs or output,
canonical-path deduplication, continue after unreadable or malformed files,
start-folder overrides may narrow folder scope only, keep the pattern catalog
operator-editable, and do not add generic plaintext API-key, token, or
unsupported secret detection as part of this feature

**Quality Gates**: `ruff check . && ruff format --check . && pyright . && pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85`; release validation also runs `python -m build` and a PyInstaller smoke test

**Scale/Scope**: Curated default coverage across user-home `.ssh`, repo-local
key/cert/config/deploy/IaC/VPN directories, and high-signal text-container
filenames, with overlapping patterns still collapsing to one canonical scan
result per file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Design Gate**: PASS

- Architecture remains inside the existing CLI, application-service, domain,
  and adapter boundaries; the feature is delivered through configuration,
  contract, fixture, and documentation updates plus any minimal scoped helper
  changes justified by tests.
- Public configuration and scope models stay typed and named around baseline
  pattern catalogs, effective scope resolution, and candidate-file discovery.
- Unit tests cover default pattern loading and scope resolution; integration and
  contract tests cover expanded default-scope behavior, start-folder narrowing,
  deduplication, and non-goal noise boundaries; coverage remains enforced at
  85% minimum.
- Quality commands remain concrete and identical for local and CI validation.
- Standalone delivery remains the same wheel plus `PyInstaller` smoke-tested
  executable, with no new packaging mechanism introduced.

**Post-Design Review**: PASS

- [research.md](./research.md), [data-model.md](./data-model.md),
  [contracts/cli-contract.md](./contracts/cli-contract.md),
  [contracts/config-contract.md](./contracts/config-contract.md), and
  [quickstart.md](./quickstart.md) preserve the existing layering, typed
  contracts, quality gates, and packaging decisions.
- The design explicitly bounds the feature to curated pattern expansion for
  currently supported key detection, excludes broad whole-home and system-root
  defaults, and does not introduce secret-leaking logs, hidden global state, or
  a generic secret-scanning subsystem.

## Project Structure

### Documentation (this feature)

```text
specs/002-expand-secret-patterns/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli-contract.md
│   └── config-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
.check-unprotected-keys.toml.example
README.md

src/
└── find_unencrypted_keys/
    ├── __init__.py
    ├── cli.py
    ├── config/
    │   ├── __init__.py
    │   ├── loader.py
    │   └── models.py
    ├── domain/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── scope.py
    │   └── classification.py
    ├── services/
    │   ├── __init__.py
    │   └── scan_service.py
    └── adapters/
        ├── __init__.py
        ├── filesystem.py
        ├── key_parsers.py
        └── reporting.py

tests/
├── contract/
│   ├── test_cli_default_scan_contract.py
│   ├── test_cli_start_folder_contract.py
│   └── test_config_contract.py
├── fixtures/
│   └── expanded-patterns/
├── integration/
│   ├── test_default_scan_workflow.py
│   └── test_start_folder_scan.py
├── support/
│   └── fixture_builders.py
└── unit/
    ├── test_config_loader.py
    ├── test_foundation_helpers.py
    ├── test_key_classification.py
    └── test_scope_resolution.py
```

**Structure Decision**: Reuse the existing single-project Python CLI layout and
concentrate the feature in the current configuration, scope-resolution,
discovery, fixture, contract, and operator-documentation surfaces. No new
runtime subsystem or package boundary is needed; the main deliverables are the
curated default catalog, tests that prove its bounded behavior, and docs that
explain how operators keep control of the expanded scope.

## Complexity Tracking

No constitutional violations or approved complexity exceptions are required for
this design.
