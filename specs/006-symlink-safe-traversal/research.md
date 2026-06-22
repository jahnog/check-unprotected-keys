# Research: Symlink-Following, Cycle-Safe Folder Traversal

**Branch**: `006-symlink-safe-traversal` | **Date**: 2026-06-22

All decisions were resolved during `/speckit-clarify`. No NEEDS CLARIFICATION items
remain. This document records each decision and its rationale for plan traceability.

---

## Decision 1 — Directory Identity Key

**Decision**: Use `(st_ino, st_dev)` inode+device number pair from `os.stat()` as the
key for the Visited-Directory Record.

**Rationale**: This is the OS-level identity of a directory. It correctly handles bind
mounts, NTFS junctions, case-insensitive filesystems, and any other aliasing the OS
permits. `os.path.realpath()` string comparison is insufficient — two paths can resolve
to different strings yet point to the same physical directory (bind mount, case-folded
name). The cost is one additional `os.stat()` syscall per subdirectory entry, which is
negligible relative to file-read operations already performed.

**Alternatives considered**:
- `os.path.realpath()` string — rejected; fails on bind mounts and case-insensitive FS
- Both combined (realpath + inode+device) — rejected; adds complexity for no correctness gain

---

## Decision 2 — Logging Verbosity for Symlink Events

**Decision**: Emit traversal events (following a symlink, skipping an already-visited
directory, skipping a broken/inaccessible link) at Python `logging.DEBUG` level only.
No output is produced at normal verbosity.

**Rationale**: The tool is a security scanner; operators care about findings, not
traversal internals. Per-symlink messages at normal verbosity would produce noise in
large trees. `DEBUG` level is the standard pattern for filesystem traversal internals.
The existing `logging` infrastructure in Python's stdlib is used; no new dependency
is required. No new CLI flag is introduced; debug output is enabled via
`logging.basicConfig(level=logging.DEBUG)` or equivalent.

**Alternatives considered**:
- Info-level for skipped/broken links — rejected; too noisy at normal verbosity
- Always silent — rejected; loses debuggability for unexpected scan gaps

---

## Decision 3 — Visited-Directory Hard Cap

**Decision**: Enforce a configurable hard cap (`scan.max_directory_visits`, default
100,000) on the visited-directory set. When the cap is reached, abort the scan
immediately and report a clear, actionable error. Exit code 2 (existing "scan could
not complete" code). No partial findings are returned.

**Rationale**: Following symlinks on untrusted or adversarially crafted filesystems
could result in unbounded directory sets. A hard cap prevents runaway memory growth and
gives operators a clear signal that the result is incomplete. The default of 100,000
directories fits typical workstation scans (at ~56 bytes per `(int, int)` tuple,
100k entries = ~5.6 MB of set memory). Operators on large enterprise mounts can raise
the limit in config. Aborting with an error is safer for a security tool than silently
returning incomplete results.

**Alternatives considered**:
- Unbounded — rejected; unsafe on adversarial filesystems
- Warn-only at threshold — rejected; silent incomplete scan is worse than a clear error

---

## Decision 4 — Windows NTFS Junction Points

**Decision**: NTFS junction points are in scope and handled transparently via the
standard library. `os.walk(followlinks=True)` and `os.stat()` treat POSIX symlinks and
NTFS junctions uniformly on Windows. No platform-specific code is introduced.

**Rationale**: The standard library already handles this. Declaring junctions "out of
scope" would create a gap for Windows users at zero implementation cost. The
`(st_ino, st_dev)` identity key works correctly for junctions on NTFS. No extra
effort is required beyond the POSIX implementation.

**Alternatives considered**:
- Explicitly out of scope — rejected; standard library handles it for free
- Best-effort with no commitment — rejected; unnecessary ambiguity

---

## Decision 5 — Visited Set Scope Across Traversal Passes

**Decision**: A single shared `VisitedDirectoryTracker` instance covers all traversal
passes in one scan (the directory-hint promotion pass inside `resolve_effective_scope`
and the candidate-file discovery pass in `discover_candidate_files`).

**Rationale**: FR-009 requires the single-visit guarantee to apply to every traversal
pass. A per-pass independent set would allow a directory entered during hint-promotion
to be entered again during candidate-file discovery, violating SC-003. The tracker is
created once in `ScanService.run()` and threaded through both calls.

**Alternatives considered**:
- Independent set per pass — rejected; violates FR-009 and SC-003

---

## Standard Library Usage

All required functionality is available in Python 3.12's standard library:

| Need | API |
|---|---|
| Follow symlinks in directory walk | `os.walk(followlinks=True)` |
| Directory identity (inode + device) | `os.stat()` → `stat.st_ino`, `stat.st_dev` |
| Detect broken/inaccessible links | `OSError` on `Path.stat()` or walk `onerror` |
| Debug-level logging | `logging.getLogger(__name__).debug(...)` |

No new runtime dependencies are required. No changes to `pyproject.toml` dependencies.
