# CLI Output Contract: Scan Warnings & Partial Results

**Feature**: `specs/010-code-quality-audit` | **Date**: 2026-07-08

The tool's external interface is the `check-unprotected-keys` CLI. This
contract defines what this feature may and may not change. Contract tests in
`tests/contract/` enforce it.

## Invariants (MUST NOT change)

- **stdout**: exactly one line per finding — `<file path>` or
  `<file path>#<property key>` — same content and order as today for all
  existing fixtures (SC-002).
- **Exit codes**: `0` no findings, `1` findings, `2` directory-visit limit
  reached. Unchanged.
- **Existing stderr lines**: `Checked N file(s). Found M violation(s).`,
  `Could not fully evaluate …`, malformed path list, remediation blocks,
  `Issue categories: …`, and the directory-limit `ERROR:` line keep their
  current wording.
- **Secret safety**: no new line may contain property values, key bytes, or
  any file content — paths, reasons, and phases only.

## Additions (stderr only)

### Skipped-location warnings (FR-001)

One line per skipped location, emitted after the issue summary, before
`Issue categories:`:

```
WARNING: skipped <path> (<reason>, during <phase>)
```

- `<reason>`: OS error type name (e.g. `PermissionError`) or diagnostic slug
  (`undecodable-content`, `unresolvable-reference`).
- `<phase>`: one of `scope-resolution`, `directory-promotion`,
  `candidate-discovery`, `file-inspection`, `reference-follow`.
- Deterministic order: sorted by path.
- A fully readable tree emits zero `WARNING: skipped` lines (Story 1,
  scenario 3).

### Partial results on limit abort (FR-002)

When the visit limit is hit, the existing `ERROR:` block is preserved and
followed by:

```
NOTE: Partial results above cover the directories visited before the limit.
```

Findings gathered before the abort are printed to stdout (previously
discarded); exit code remains `2` even if findings exist (limit dominates).

## Contract test obligations

- `tests/contract/test_cli_default_scan_contract.py`: extend to assert zero
  `WARNING: skipped` lines on the clean fixture tree.
- New `tests/contract/test_cli_skip_warnings_contract.py`: unreadable
  directory + unreadable file + dangling `.properties` reference fixture →
  exact warning lines, stdout unchanged, exit code unchanged.
- Limit-abort contract: tiny `max_directory_visits` over a fixture with an
  early finding → finding on stdout, `ERROR:` + `NOTE:` on stderr, exit 2.
