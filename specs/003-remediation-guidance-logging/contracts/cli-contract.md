# CLI Contract: Remediation Guidance Logging

## Command

`check-unprotected-keys [--start-folder PATH]`

## Purpose

Scan configured folders and filename patterns for currently supported
unprotected private-key material, print one canonical affected-file path per
finding to stdout, and print operator-facing malformed-file review gaps and
remediation guidance to stderr.

## Inputs

### Option: `--start-folder PATH`

- Optional.
- Accepts either an absolute path or a path relative to the execution root.
- Narrows reachable configured folder roots beneath `PATH`.
- Does not change filename-pattern matching, malformed-file handling, or
  remediation-guidance behavior.

## Output Contract

### Standard Output

- One line per unprotected finding.
- Each line contains only the canonical absolute path of the affected file.
- No malformed-file logs, recommendation text, summaries, secret values, key
  material, or classifications may appear on stdout.

### Standard Error

- Emits the existing scan summary line showing files checked and findings found.
- Emits aggregate malformed and unreadable summaries when applicable.
- Emits one operator-safe malformed-file path entry for each malformed file.
- Emits operator-safe remediation guidance for each unprotected finding.
- Emits stderr sections in stable discovery order: summary, malformed/unreadable
  review gaps, malformed file paths, per-finding remediation blocks, then safe
  issue-category aggregates.
- May include configuration or usage error messages.
- Must not echo secret values, raw file contents, passphrases, or private-key
  material.

## Exit Codes

- `0`: Scan completed and no unprotected findings were found.
- `1`: One or more unprotected findings were found.
- `2`: The command could not execute because CLI arguments or configuration were
  invalid.

## Behavioral Guarantees

- Malformed files do not become findings solely because they are malformed.
- Malformed-file logging does not alter the machine-readable stdout stream.
- Remediation guidance is advisory only; the CLI does not rewrite, encrypt,
  rotate, upload, or delete keys.
- Guidance is generated only for currently supported unprotected key findings.
- User SSH identity files may receive session-oriented passphrase plus agent
  guidance.
- SSH host key files may receive host-specific hardening or reprovisioning
  guidance and must not receive advice that assumes an interactive prompt is
  acceptable during service startup.
- Embedded-key text containers may receive vault or secret-manager guidance
  that recommends removing the key from the file and referencing external
  secret storage instead.
- `--start-folder` narrows both finding output and remediation guidance to the
  matching subtree without changing stderr section ordering.
- Existing `--start-folder` semantics, canonical-path reporting, and exit-code
  behavior remain unchanged.