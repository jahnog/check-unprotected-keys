# CLI Contract: Expand Secret Patterns

## Command

`check-unprotected-keys [--start-folder PATH]`

## Purpose

Scan the configured folder and filename scope for currently supported private
key material, including supported key blocks embedded in matched text files,
and print one canonical file path per affected file.

## Inputs

### Option: `--start-folder PATH`

- Optional.
- Accepts either an absolute path or a path relative to the execution root.
- When supplied, it narrows folder-pattern expansion to matching configured
  folders beneath `PATH`.
- It MUST NOT change the configured filename-pattern list, including the
  expanded default catalog.

## Runtime Configuration

- The command loads `.check-unprotected-keys.toml` from the execution root.
- The shipped `.check-unprotected-keys.toml.example` documents the expanded
  default folder and filename catalog.
- Configuration may include curated `~`-prefixed roots such as `~/.ssh`.
- Configuration load or validation failures are treated as invocation errors.

## Output Contract

### Standard Output

- One line per affected file.
- Each line contains only the canonical absolute path of the file.
- No key contents, passphrases, algorithm details, token values, or raw line
  values may be emitted.

### Standard Error

- May contain operator-safe summaries for malformed or unreadable files.
- May contain configuration or usage error messages.
- Must not echo secret values.

## Exit Codes

- `0`: Scan completed and no affected files were found.
- `1`: One or more affected files were found.
- `2`: The command could not execute because CLI arguments or configuration were
  invalid.

## Behavioral Guarantees

- No new CLI flags are introduced by this feature.
- The expanded default catalog widens candidate discovery only; it does not
  change output formatting or error semantics.
- A valid `--start-folder` narrows reachable folder roots only.
- Filename matching remains unchanged after start-folder narrowing.
- Each affected file is reported at most once per scan.
- Files containing only public keys are never reported as findings.
- Unreadable or malformed files are not converted into findings.
- The command continues scanning remaining files after a per-file read or parse
  failure.
- The expanded catalog does not imply generic plaintext API-key, token, or
  unsupported secret detection; only the existing supported key-material
  exposure rules apply.