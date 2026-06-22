# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog and the project uses Semantic Versioning.

## [Unreleased]

### Added

- symbolic links are now followed during recursive directory traversal; cycles and aliased directories are handled automatically via an inode+device single-visit guarantee, and a configurable `scan.max_directory_visits` hard cap (default 100,000) aborts with exit code 2 when reached
- packaged example configuration available through `--print-example-config`
- `python -m check_unprotected_keys` module entrypoint support
- release validation guide and automated publish workflow

### Changed

- package metadata now includes publish-oriented classifiers, keywords, and URLs
- CI now runs through the same `uv`-based validation commands used locally
- PyInstaller builds now bundle packaged runtime resources needed by the CLI

## [0.1.0] - 2026-06-07

### Added

- standalone CLI for detecting unprotected PEM, OpenSSH, PuTTY, and embedded key material
- contract, integration, and unit coverage for the CLI scan workflow
- standalone executable smoke test driven by `check-unprotected-keys.spec`
- MIT license and release validation documentation