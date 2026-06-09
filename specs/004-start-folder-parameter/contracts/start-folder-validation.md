# Start Folder Validation Contract (Unit-Testable Seam)

**Related**: The full CLI surface contract is documented in `specs/001-check-unprotected-keys/contracts/cli-contract.md` (the `--start-folder PATH` option section). This document focuses on the narrow validation seam that the new unit tests must enforce.

## Function Under Contract

`resolve_start_folder(execution_root: Path, raw_value: str | None) -> Path | None`

## Inputs

- `execution_root`: a resolved absolute `Path` representing the directory from which the CLI was invoked (normally `Path.cwd().resolve()`).
- `raw_value`:
  - `None` — parameter was omitted on the command line.
  - `str` — the literal value supplied after `--start-folder` (may be relative, absolute, or contain `~`).

## Success Outputs

- When `raw_value is None`: return `None` (signals "use full configured scope").
- When `raw_value` is a valid path:
  - Perform `~` expansion.
  - If not absolute, join with `execution_root`.
  - `.resolve()` the candidate.
  - The resolved path MUST exist, be a directory, and be readable.
  - Return the canonical resolved `Path`.

## Error Outputs

All errors are raised as `ValueError` (the CLI catches `ValueError` together with `ConfigurationError` and turns them into exit code 2 + `emit_error`).

Exact message prefixes that callers and tests may assert:

- `f"Start folder does not exist: {resolved}"`
- `f"Start folder is not a directory: {resolved}"`
- `f"Start folder is not readable: {resolved}"`

The resolved path appears in the message so operators see what was actually evaluated after expansion and resolution.

## Guarantees (the four states required by the feature spec)

1. **Omitted**: `resolve_start_folder(root, None) is None` — no error, full scope proceeds.
2. **Passed (valid)**: A syntactically valid relative or absolute path that resolves to an existing readable directory returns the canonical Path without raising.
3. **Valid**: After resolution the directory check + readability check both pass.
4. **Invalid**: Any of the three failure modes above raises immediately with the documented message; the function performs no further I/O that would belong to scanning (no config load, no glob, no walk).

## Non-Goals (out of scope for this seam)

- Interpretation of the value against configured folder patterns (that happens later in `resolve_effective_scope` + `narrow_root_directories`).
- Changes to filename patterns.
- Any user-visible help text or argparse definition (those belong to the CLI contract in 001).

## Test Implications

Unit tests for this contract must directly import and call `resolve_start_folder`, supply crafted `execution_root` + `raw_value`, and assert either the exact return value or the exact exception message. They must cover the four states without going through `cli.main` or the full scan pipeline (those are the responsibility of contract and integration tests).

This contract is intentionally small and pure enough to be exercised in fast unit tests with real but temporary filesystem objects.