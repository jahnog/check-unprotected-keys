# Data Model: Symlink-Following, Cycle-Safe Folder Traversal

**Branch**: `006-symlink-safe-traversal` | **Date**: 2026-06-22

---

## New Infrastructure Class — `VisitedDirectoryTracker`

**Layer**: Infrastructure adapter (`adapters/filesystem.py`)

**Purpose**: Enforces the single-visit guarantee and hard cap for directory traversal.
Created once per scan in `ScanService.run()` and passed into all traversal functions.

### Fields

| Field | Type | Description |
|---|---|---|
| `_visited` | `set[tuple[int, int]]` | Set of `(st_ino, st_dev)` pairs for seen directories |
| `_limit` | `int` | Maximum allowed directory visits (from `SearchConfiguration.max_directory_visits`) |

### Methods

| Method | Signature | Behaviour |
|---|---|---|
| `try_visit` | `(path: Path) -> bool` | Stat the path; add `(st_ino, st_dev)` to `_visited` and return `True` if new. Return `False` if already seen. Raise `OSError` if path cannot be stat'd (broken link). Raise `DirectoryLimitExceededError` if `len(_visited) >= _limit` before adding. |
| `visited_count` | `property -> int` | Number of distinct directories recorded so far. |

### Identity semantics

The key `(stat.st_ino, stat.st_dev)` is obtained via `path.stat()` (follows symlinks).
Two paths sharing the same inode on the same device are treated as the same directory,
correctly handling bind mounts, NTFS junctions, and case-insensitive aliasing.

---

## New Exception — `DirectoryLimitExceededError`

**Layer**: Infrastructure adapter (`adapters/filesystem.py`)

Raised by `VisitedDirectoryTracker.try_visit` when the visited-directory count reaches
the configured hard cap. Caught by `ScanService.run()`.

### Fields

| Field | Type | Description |
|---|---|---|
| `limit` | `int` | The cap that was reached |
| `path` | `Path` | The directory that triggered the cap |

---

## Modified Domain Model — `SearchConfiguration`

**Layer**: Domain (`domain/models.py`)

Added field:

| Field | Type | Default | Description |
|---|---|---|---|
| `max_directory_visits` | `int` | `100_000` | Hard cap on distinct directories visited per scan. Configurable via `scan.max_directory_visits` in the TOML config. |

---

## Modified Config Model — `ScanConfigSection`

**Layer**: Config (`config/models.py`)

Added field (mirrors `SearchConfiguration`):

| Field | Type | Default | Description |
|---|---|---|---|
| `max_directory_visits` | `int` | `100_000` | Loaded from `scan.max_directory_visits`; validated as a positive integer. |

---

## Modified Domain Model — `ScanResult`

**Layer**: Domain (`domain/models.py`)

Added field:

| Field | Type | Default | Description |
|---|---|---|---|
| `directory_limit_exceeded` | `bool` | `False` | Set to `True` when `DirectoryLimitExceededError` is caught during traversal. |

Updated property:

| Property | Before | After |
|---|---|---|
| `exit_code` | `1 if findings else 0` | `2 if directory_limit_exceeded else (1 if findings else 0)` |

---

## Modified Function Signatures — `adapters/filesystem.py`

All three traversal functions gain a `visited_tracker` keyword argument:

```
resolve_effective_scope(
    configuration: SearchConfiguration,
    *,
    start_folder: Path | None,
    visited_tracker: VisitedDirectoryTracker,          # NEW
) -> EffectiveScope

discover_candidate_files(
    scope: EffectiveScope,
    *,
    visited_tracker: VisitedDirectoryTracker,          # NEW
) -> tuple[list[CandidateFile], list[DiscoveryIssue]]

_discover_promoted_directories(
    bases: list[Path] | tuple[Path, ...],
    directory_names: tuple[str, ...],
    ignore_names: frozenset[str],
    *,
    start_folder: Path | None = None,
    visited_tracker: VisitedDirectoryTracker,          # NEW
) -> tuple[list[Path], dict[Path, str]]
```

The `followlinks` argument in both `os.walk` calls changes from `False` to `True`.

---

## Traversal Algorithm (per walk invocation)

```
Before os.walk starts on root_directory:
  1. try_visit(root_directory)
     → False (already visited): skip this walk entirely (root was entered in hint pass)
     → True: mark as visited, proceed
     → DirectoryLimitExceededError: propagate up

During os.walk (topdown=True, followlinks=True):
  For each subdirectory `d` in dirnames:
    sub_path = current_path / d
    try:
      result = tracker.try_visit(sub_path)
      if result is False:
        logger.debug("skipping already-visited: %s", sub_path)
        prune `d` from dirnames
      # else: keep `d` for descent
    except DirectoryLimitExceededError:
      raise  # propagate to ScanService
    except OSError as exc:
      logger.debug("skipping inaccessible link: %s (%s)", sub_path, exc)
      prune `d` from dirnames
      append DiscoveryIssue if in discover_candidate_files
```

---

## Configuration Schema Addition

New optional key in the `[scan]` TOML table:

```toml
# max_directory_visits = 100000
```

- Type: positive integer
- Default: `100_000`
- Validation: must be an integer ≥ 1; if present and invalid, raises `ConfigurationError`
- Effect: hard cap on `VisitedDirectoryTracker._limit`

---

## Layer Boundaries (constitution compliance)

| Concern | Layer | Location |
|---|---|---|
| `VisitedDirectoryTracker` | Infrastructure adapter | `adapters/filesystem.py` |
| `DirectoryLimitExceededError` | Infrastructure adapter | `adapters/filesystem.py` |
| `max_directory_visits` config field | Domain / Config | `domain/models.py`, `config/models.py` |
| `directory_limit_exceeded` result field | Domain | `domain/models.py` |
| Tracker construction + exception catch | Application service | `services/scan_service.py` |
| Limit-exceeded error output | Adapter (reporting) | `adapters/reporting.py` |

Domain and service layers do not import OS-level primitives.
The tracker (OS identity) lives exclusively in the filesystem adapter.
`DirectoryLimitExceededError` crosses from adapter to service — this is the existing
cross-layer pattern already in place (`adapters` imported directly in `scan_service.py`).
