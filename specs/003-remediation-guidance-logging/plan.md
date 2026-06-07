# Implementation Plan: Remediation Guidance Logging

**Branch**: `[003-remediation-guidance-logging]` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-remediation-guidance-logging/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Extend the existing scan reporting flow so the CLI logs malformed file paths to
the operator-facing console stream and attaches low-friction remediation
guidance to unprotected findings based on inferred usage category, while
preserving the current machine-readable stdout contract, exit codes, layered
architecture, and standalone packaging workflow.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `cryptography` for supported key parsing and
classification; Python standard library modules `argparse`, `dataclasses`,
`enum`, `pathlib`, and `textwrap`; no new third-party runtime dependency is
required for advisory guidance generation

**Storage**: N/A; read-only local filesystem scan input plus root-level
`.check-unprotected-keys.toml` configuration and operator-facing console output

**Testing**: `pytest`, `pytest-cov`, CLI contract tests, integration tests for
end-to-end scan output, and focused unit tests for recommendation selection and
malformed-path reporting

**Target Platform**: Linux x86_64 local filesystems first, with the existing
portable path handling preserved

**Project Type**: Standalone CLI security scanner

**Packaging/Distribution**: `setuptools` console script for development and
wheel builds, plus a `PyInstaller` standalone executable smoke-tested during
release validation

**Performance Goals**: Preserve current scan throughput characteristics by
keeping added work bounded to lightweight per-finding and per-malformed-file
report construction, with no extra filesystem traversal or file-content rescans

**Constraints**: Findings on stdout must remain one canonical path per line,
operator-facing logs must remain on stderr, no secret material or raw file
contents may be echoed, malformed files must not change exit-code semantics,
guidance must stay advisory only, and the feature must not expand into generic
token or password detection

**Quality Gates**: `uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pyright . && uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85`; release validation also runs `uv run --extra dev python -m build` and `uv run --extra dev bash scripts/smoke_test_executable.sh`

**Scale/Scope**: Existing repo-scale and workstation-scale scans across
thousands of candidate files, with additional guidance emitted only for the
subset of unprotected findings and malformed files already discovered by the
current pipeline

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Design Gate**: PASS

- The feature stays within the existing CLI, service, domain, and adapter
  layers: domain models gain typed reporting metadata, the scan service derives
  safe recommendation context, and the reporting adapter controls stream
  formatting.
- Public interfaces remain typed through `ScanResult`, `KeyFinding`, and any
  added usage-category or recommendation DTOs; no hidden global state or
  implicit side channels are introduced.
- Unit tests are planned for malformed-path capture and recommendation mapping;
  contract and integration tests are planned for stdout/stderr separation and
  unchanged exit-code behavior; coverage remains enforced at 85% minimum.
- Local and CI quality commands remain concrete and identical through the
  existing `uv run --extra dev` toolchain.
- Standalone delivery remains the same wheel plus `PyInstaller` executable,
  with no new packaging mechanism and with smoke-test validation preserved.

**Post-Design Review**: PASS

- [research.md](./research.md), [data-model.md](./data-model.md),
  [contracts/cli-contract.md](./contracts/cli-contract.md), and
  [quickstart.md](./quickstart.md) preserve the current layered architecture and
  keep recommendation generation advisory, typed, and secret-safe.
- The design explicitly preserves machine-readable stdout, avoids adding any
  network dependency or automatic secret migration behavior, and documents the
  distinct handling required for interactive user keys, host keys, automation
  keys, and embedded-key configuration files.

## Project Structure

### Documentation (this feature)

```text
specs/003-remediation-guidance-logging/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── check_unprotected_keys/
    ├── cli.py
    ├── domain/
    │   └── models.py
    ├── services/
    │   └── scan_service.py
    └── adapters/
        ├── key_parsers.py
        └── reporting.py

tests/
├── contract/
│   └── test_cli_default_scan_contract.py
├── integration/
│   └── test_default_scan_workflow.py
└── unit/
    ├── test_malformed_path_logging.py
    └── test_remediation_guidance.py
```

**Structure Decision**: Reuse the existing single-project Python CLI layout and
implement the feature in the current reporting slice. The smallest coherent
change is to extend typed scan-result metadata in the domain, assemble
malformed-path and recommendation information in the scan service from existing
candidate metadata, and keep all user-visible rendering inside the reporting
adapter. This avoids adding a new subsystem while keeping tests aligned with
the current CLI contract.

## Complexity Tracking

No constitutional violations or approved complexity exceptions are required for
this design.