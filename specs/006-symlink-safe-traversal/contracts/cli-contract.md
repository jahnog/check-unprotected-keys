# CLI Contract: Symlink-Following, Cycle-Safe Folder Traversal

**Branch**: `006-symlink-safe-traversal` | **Date**: 2026-06-22

This document describes the observable CLI contract changes introduced by this feature.
The existing contract (arguments, stdout format, exit codes 0 and 1) is unchanged.
Only additions are documented here.

---

## New Configuration Key

### `scan.max_directory_visits` (optional integer)

Added to the `[scan]` TOML table. Controls the hard cap on distinct directories the
scanner may visit in a single run.

```toml
[scan]
# Maximum distinct directories to visit per scan.
# If exceeded the scan aborts and reports an error. Default: 100000.
# max_directory_visits = 100000
```

**Type**: positive integer (`>= 1`)
**Default**: `100000`
**Validation**: if present and not a positive integer, raises `ConfigurationError`
(same as other invalid config values — exits with code 2, message on stderr).

---

## New Behaviour: Symlink Following

Symbolic links to directories are now followed during traversal. This is automatic
(default-on) and requires no configuration change. Links to files are evaluated as
candidate files. Broken or inaccessible links are silently skipped.

---

## New Exit Code Scenario: Directory Limit Exceeded

| Code | Meaning | When |
|---|---|---|
| `0` | Clean scan — no violations | (unchanged) |
| `1` | Violations found | (unchanged) |
| `2` | Scan could not complete | (unchanged: config error) + **NEW: directory limit exceeded** |

### Stderr output when limit exceeded

```
ERROR: Scan aborted — directory visit limit (100000) reached. Results are incomplete.
Raise scan.max_directory_visits in your configuration to scan larger trees,
or narrow the search scope with --start-folder.
```

Stdout: empty (no partial findings are reported).

---

## Unchanged Contract Elements

- All existing CLI arguments (`--start-folder`, `--version`, `--print-example-config`)
- Stdout format: one canonical file path per line per finding
- Stderr format for summaries and remediation guidance
- Exit codes 0 and 1
- All existing TOML configuration keys
- Standalone binary packaging and entry point
