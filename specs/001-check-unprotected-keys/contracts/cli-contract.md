# CLI Contract: Check Unprotected Keys

## Command

`check-unprotected-keys [--start-folder PATH]`

## Purpose

Scan the configured folder and filename scope for supported private-key material
and print one canonical file path per file that contains unprotected private
keys.

## Inputs

### Option: `--start-folder PATH`

- Optional.
- Accepts either an absolute path or a path relative to the execution root.
- When supplied, it narrows folder-pattern expansion to matching configured
  folders beneath `PATH`.
- It MUST NOT change the configured filename-pattern list.

## Runtime Configuration

- The command loads `.check-unprotected-keys.toml` from the execution root.
- Configuration load or validation failures are treated as invocation errors.

## Output Contract

### Standard Output

- One line per affected file.
- Each line contains only the canonical absolute path of the file.
- No key contents, passphrases, algorithm details, or raw line values may be
  emitted.

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

- Each affected file is reported at most once per scan.
- Files containing only public keys are never reported as findings.
- Unreadable or malformed files are not converted into findings.
- The command continues scanning remaining files after a per-file read or parse
  failure.