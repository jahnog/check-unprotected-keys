# Quickstart Validation: Code Quality Audit Remediation

**Feature**: `specs/010-code-quality-audit` | **Date**: 2026-07-08

Runnable scenarios proving the feature end-to-end. Contracts:
[cli-output.md](./contracts/cli-output.md),
[extension-points.md](./contracts/extension-points.md). Entities:
[data-model.md](./data-model.md).

## Prerequisites

```bash
cd /path/to/CheckUnprotectedKeys
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## 1. Quality gates (SC-006) — run after every work item

```bash
pytest                      # unit+integration+contract, coverage ≥85% enforced
ruff check .
ruff format --check .
pyright
```

Expected: all pass; coverage does not drop below the pre-feature value.

## 2. Regression identity (SC-002)

```bash
pytest tests/integration tests/contract
```

Expected: golden stdout assertions (WI-1) pass unchanged after every
refactor WI — findings byte-identical, only new stderr `WARNING:`/`NOTE:`
lines differ where fixtures contain injected faults.

## 3. Skipped locations are observable (SC-001, Story 1)

```bash
SCRATCH=$(mktemp -d)
mkdir -p "$SCRATCH/keys/hidden"
ssh-keygen -t ed25519 -N '' -f "$SCRATCH/keys/id_ed25519" -q
chmod 000 "$SCRATCH/keys/hidden"          # unreadable directory
check-unprotected-keys --start-folder "$SCRATCH" ; echo "exit=$?"
chmod 755 "$SCRATCH/keys/hidden"; rm -rf "$SCRATCH"
```

Expected: stdout lists the unprotected key; stderr contains exactly one
`WARNING: skipped .../keys/hidden (PermissionError, during candidate-discovery)`;
exit=1. Re-run with the directory readable: zero WARNING lines. Automated in
`tests/integration/test_unreadable_tree_scan.py` (fault-injection asserts the
N-locations/N-warnings equality).

## 4. Partial results on limit abort (FR-002)

Automated: contract test sets `scan.max_directory_visits` tiny over a fixture
with an early finding. Expected: finding still on stdout, `ERROR:` block plus
`NOTE: Partial results…` on stderr, exit code 2.

## 5. Extension points (SC-003, Story 2)

```bash
pytest tests/unit/test_detection_registries.py -v
```

Expected: the demo test registers a dummy key recognizer via the registry
only, scans a fixture where it fires, asserts participation, then restores the
registry and asserts baseline behavior — with zero modifications to existing
detection units. Completeness invariants (every `UsageCategory` defined once;
rule order matches contract) pass.

## 6. Orchestrator + parser coverage (SC-004, Story 3)

```bash
pytest tests/unit/test_scan_service_orchestration.py \
       tests/unit/test_key_parsers.py --cov --cov-report=term-missing
```

Expected: orchestrator limit/malformed/unreadable branches exercised with
in-memory fakes (no real filesystem); per-format parser paths (valid,
encrypted, malformed, truncated) directly covered; module report shows
`key_parsers.py` and `scan_service.py` coverage above pre-feature values.

Module-size check (SC-004):

```bash
wc -l src/check_unprotected_keys/**/*.py | sort -n | tail -5
```

Expected: no production module over ~400 lines.

## 7. Single-source default (SC-005, Story 4)

```bash
grep -rn "100_000" src/
```

Expected: exactly one hit — `DEFAULT_MAX_DIRECTORY_VISITS` in
`domain/models.py`. A unit test changes the constant via monkeypatch and
asserts loader default and tracker limit follow.

## 8. Packaging smoke (NFR-004 — unchanged)

```bash
pyinstaller --onefile --name check-unprotected-keys src/check_unprotected_keys/__main__.py
./dist/check-unprotected-keys --help
```

Expected: builds and runs exactly as before this feature.
