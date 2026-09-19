# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-07-08

### Added

- Skipped locations (unreadable directories, unreadable files, unresolvable
  key references) are now reported on stderr as
  `WARNING: skipped <path> (<reason>, during <phase>)`, sorted by path and
  emitted once per location.
- When `scan.max_directory_visits` aborts a scan, findings collected so far are
  still printed and stderr ends with a `NOTE:` line explaining the partial
  result.
- Dedicated unit coverage for key parsers, filesystem traversal, skipped
  location reporting, and `ScanService` orchestration.

### Changed

- Detection dispatch for key formats, usage categories, remediation guidance,
  and the properties inspection pipeline is now registry-driven.
- `domain/properties.py` was split into a `domain/properties/` package
  (parser, bundles, locales, shapes, signatures, tiers, reference data).
- `ScanService` collaborators are injected through `services/ports.py`
  protocols.
- The directory-visit limit default is declared in a single place.
- Bumped the `cryptography` dependency.

## [1.0.0] - 2026-06-23

### Added

- Java `.properties` inspection: plaintext credentials under secret-named keys
  (token-aware, STRONG/WEAK grading), values matching known secret signatures,
  inline private-key material, and paths that resolve to unprotected key
  files. Property findings are reported as `<path>#<property key>`; values
  are never printed.
- `scan.property_name_patterns` and `scan.property_value_ignore`
  configuration keys.
- Message/resource bundles (locale-suffixed or known base names) are exempt
  from name-based credential matching.
- `scan.ignore_directories` and `scan.ignore_filename_patterns` configuration
  keys with omit / `[]` / replace semantics; the packaged ignore lists are no
  longer hard-coded.
- `scan.base_folders` search bases and `scan.directory_names` promotion hints
  replace the single `folder_patterns` list, which remains accepted as a
  legacy alias.
- Symbolic links are followed during traversal; cycles and aliased
  directories are visited once (inode + device guard) and
  `scan.max_directory_visits` (default 100,000) aborts runaway scans with
  exit code `2`.
- `--start-folder` option to narrow a scan to a subtree while keeping the
  configured filename patterns.
- Remediation guidance on stderr for each finding and operator-safe reporting
  of malformed or unreadable files.
- Expanded default filename catalog (`.env*`, `*.ovpn`, `*.tfvars`,
  `*.properties`, SSH host keys, PuTTY keys).
- Packaged example configuration available through `--print-example-config`.
- `python -m check_unprotected_keys` module entrypoint.
- Release validation guide and automated publish workflow.

### Changed

- Package metadata now includes publish-oriented classifiers, keywords, and
  URLs.
- CI runs the same `uv`-based validation commands used locally.
- PyInstaller builds bundle the packaged runtime resources needed by the CLI.

## [0.1.0] - 2026-06-07

### Added

- Standalone CLI for detecting unprotected PEM, OpenSSH, PuTTY, and embedded
  key material.
- Contract, integration, and unit coverage for the CLI scan workflow.
- Standalone executable smoke test driven by `check-unprotected-keys.spec`.
- MIT license and release validation documentation.
